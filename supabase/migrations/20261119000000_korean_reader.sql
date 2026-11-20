begin;

create table public.korean_documents (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null default auth.uid() references auth.users on delete cascade,
    title text not null check (char_length(title) between 1 and 120),
    original_text text not null check (char_length(original_text) between 1 and 800),
    source text check (char_length(source) <= 180),
    content_hash text not null,
    analysis_version text not null,
    analysis jsonb not null,
    created_at timestamptz not null default now(),
    unique (user_id, content_hash, analysis_version),
    unique (user_id, id)
);

create table public.korean_import_claims (
    user_id uuid not null default auth.uid() references auth.users on delete cascade,
    content_hash text not null,
    analysis_version text not null,
    lease uuid not null,
    expires_at timestamptz not null,
    primary key (user_id, content_hash, analysis_version)
);

create table public.korean_concepts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null default auth.uid() references auth.users on delete cascade,
    kind text not null check (kind in ('lexical', 'particle', 'morphology', 'construction')),
    form text not null,
    sense text not null,
    meaning text not null,
    created_at timestamptz not null default now(),
    unique (user_id, id)
);

create table public.korean_concept_aliases (
    user_id uuid not null default auth.uid(),
    alias_key text not null,
    concept_id uuid not null,
    primary key (user_id, alias_key),
    foreign key (user_id, concept_id) references public.korean_concepts (user_id, id) on delete cascade
);

create table public.korean_user_knowledge (
    user_id uuid not null default auth.uid(),
    concept_id uuid not null,
    recognition_state text not null default 'learning' check (recognition_state in ('known', 'learning')),
    production_state text not null default 'unpracticed'
        check (production_state in ('unpracticed', 'practiced', 'needs_practice')),
    updated_at timestamptz not null default now(),
    primary key (user_id, concept_id),
    foreign key (user_id, concept_id) references public.korean_concepts (user_id, id) on delete cascade
);

create table public.korean_practice_sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null default auth.uid(),
    document_id uuid not null,
    exercises jsonb not null check (jsonb_array_length(exercises) = 5),
    created_at timestamptz not null default now(),
    unique (user_id, id),
    foreign key (user_id, document_id) references public.korean_documents (user_id, id) on delete cascade
);

create table public.korean_exercise_attempts (
    user_id uuid not null default auth.uid(),
    session_id uuid not null,
    position integer not null check (position between 0 and 4),
    answer text not null check (char_length(answer) between 1 and 280),
    result jsonb not null,
    created_at timestamptz not null default now(),
    primary key (user_id, session_id, position),
    foreign key (user_id, session_id) references public.korean_practice_sessions (user_id, id) on delete cascade
);

create index korean_practice_documents on public.korean_practice_sessions (user_id, document_id);
create index korean_alias_concepts on public.korean_concept_aliases (user_id, concept_id);

do $$
declare
    relation regclass;
begin
    foreach relation in array array[
        'public.korean_documents'::regclass, 'public.korean_import_claims'::regclass,
        'public.korean_concepts'::regclass, 'public.korean_concept_aliases'::regclass,
        'public.korean_user_knowledge'::regclass, 'public.korean_practice_sessions'::regclass,
        'public.korean_exercise_attempts'::regclass
    ] loop
        execute format('alter table %s enable row level security', relation);
        execute format('revoke all on %s from public, anon, authenticated', relation);
        execute format('grant select, insert on %s to authenticated', relation);
        execute format(
            'create policy korean_owner on %s for all to authenticated
             using (user_id = (select auth.uid()) and coalesce((select auth.jwt())->>''is_anonymous'', ''false'') = ''false'')
             with check (user_id = (select auth.uid()) and coalesce((select auth.jwt())->>''is_anonymous'', ''false'') = ''false'')',
            relation
        );
    end loop;
end
$$;

grant delete on public.korean_documents, public.korean_import_claims to authenticated;
grant update on public.korean_user_knowledge to authenticated;

create function public.korean_claim_import(p_hash text, p_version text, p_lease uuid)
returns boolean
language plpgsql
set search_path = ''
as $$
declare
    owner_id uuid := auth.uid();
begin
    -- Serialize brief claim and save transactions per owner, never the model request.
    perform pg_advisory_xact_lock(hashtextextended(owner_id::text, 0));
    delete from public.korean_import_claims where user_id = owner_id and expires_at <= now();
    insert into public.korean_import_claims (user_id, content_hash, analysis_version, lease, expires_at)
    select owner_id, p_hash, p_version, p_lease, now() + interval '2 minutes'
    where not exists (
        select 1 from public.korean_documents where user_id = owner_id
        and content_hash = p_hash and analysis_version = p_version
    )
    on conflict do nothing;
    return found;
end
$$;

-- Consume the import lease and resolve concept IDs in the same transaction as the document.
create function public.korean_save_document(
    p_hash text, p_version text, p_lease uuid, p_title text, p_text text, p_source text,
    p_translation text, p_concepts jsonb, p_annotations jsonb
)
returns uuid
language plpgsql
set search_path = ''
as $$
declare
    owner_id uuid := auth.uid();
    concept jsonb;
    concept_id uuid;
    alias_ids uuid[];
    concept_ids uuid[] := '{}';
    annotations jsonb;
    document_id uuid;
begin
    perform pg_advisory_xact_lock(hashtextextended(owner_id::text, 0));
    delete from public.korean_import_claims where user_id = owner_id and content_hash = p_hash
        and analysis_version = p_version and lease = p_lease and expires_at > now();
    if not found then
        return null;
    end if;

    select id into document_id from public.korean_documents where user_id = owner_id
        and content_hash = p_hash and analysis_version = p_version;
    if found then
        return document_id;
    end if;

    for concept in select value from jsonb_array_elements(p_concepts) loop
        select a.concept_id into concept_id from public.korean_concept_aliases a
        where a.user_id = owner_id and a.alias_key = concept->>'key';
        if concept_id is null then
            select array_agg(distinct a.concept_id) into alias_ids
            from public.korean_concept_aliases a
            where a.user_id = owner_id and (concept->'alias_keys') ? a.alias_key;
            if cardinality(alias_ids) = 1 then
                concept_id := alias_ids[1];
            else
                insert into public.korean_concepts (user_id, kind, form, sense, meaning)
                values (owner_id, concept->>'kind', concept->>'form', concept->>'sense', concept->>'meaning')
                returning id into concept_id;
            end if;
        end if;
        insert into public.korean_concept_aliases (user_id, concept_id, alias_key)
        select owner_id, concept_id, value
        from jsonb_array_elements_text((concept->'alias_keys') || jsonb_build_array(concept->>'key'))
        on conflict do nothing;
        concept_ids := array_append(concept_ids, concept_id);
    end loop;

    select jsonb_agg((a.value - 'concept_refs') || jsonb_build_object('concept_ids', (
        select jsonb_agg(distinct concept_ids[(ref.value::integer) + 1])
        from jsonb_array_elements_text(a.value->'concept_refs') as ref
    )) order by a.ordinality) into annotations
    from jsonb_array_elements(p_annotations) with ordinality as a;

    insert into public.korean_documents
        (user_id, title, original_text, source, content_hash, analysis_version, analysis)
    values (owner_id, p_title, p_text, p_source, p_hash, p_version,
        jsonb_build_object('translation', p_translation, 'annotations', annotations))
    returning id into document_id;
    return document_id;
end
$$;

create function public.korean_record_attempt(p_session uuid, p_position integer, p_answer text, p_result jsonb)
returns boolean
language plpgsql
set search_path = ''
as $$
declare
    owner_id uuid := auth.uid();
    targets jsonb;
begin
    select exercises->p_position->'concept_ids' into targets from public.korean_practice_sessions
    where id = p_session and user_id = owner_id;
    if targets is null then
        return false;
    end if;

    insert into public.korean_exercise_attempts (user_id, session_id, position, answer, result)
    values (owner_id, p_session, p_position, p_answer, p_result)
    on conflict do nothing;
    if not found then
        return false;
    end if;

    insert into public.korean_user_knowledge (user_id, concept_id, production_state)
    select owner_id, value::uuid,
        case when (p_result->>'correct')::boolean then 'practiced' else 'needs_practice' end
    from jsonb_array_elements_text(targets)
    order by value
    on conflict (user_id, concept_id) do update
    set production_state = excluded.production_state, updated_at = now();
    return true;
end
$$;

revoke all on function public.korean_claim_import(text, text, uuid) from public, anon, authenticated;
revoke all on function public.korean_save_document(text, text, uuid, text, text, text, text, jsonb, jsonb)
    from public, anon, authenticated;
revoke all on function public.korean_record_attempt(uuid, integer, text, jsonb) from public, anon, authenticated;
grant execute on function public.korean_claim_import(text, text, uuid) to authenticated;
grant execute on function public.korean_save_document(text, text, uuid, text, text, text, text, jsonb, jsonb)
    to authenticated;
grant execute on function public.korean_record_attempt(uuid, integer, text, jsonb) to authenticated;

commit;
