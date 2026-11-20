begin;

create or replace function public.korean_claim_import(p_hash text, p_version text, p_lease uuid)
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
    select owner_id, p_hash, p_version, p_lease, now() + interval '4 minutes'
    where not exists (
        select 1 from public.korean_documents where user_id = owner_id
        and content_hash = p_hash and analysis_version = p_version
    )
    on conflict do nothing;
    return found;
end
$$;

create function public.korean_resolve_annotations(p_concepts jsonb, p_annotations jsonb)
returns jsonb
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
begin
    perform pg_advisory_xact_lock(hashtextextended(owner_id::text, 0));
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

    return annotations;
end
$$;

revoke all on function public.korean_resolve_annotations(jsonb, jsonb) from public, anon, authenticated;
grant execute on function public.korean_resolve_annotations(jsonb, jsonb) to authenticated;

create or replace function public.korean_save_document(
    p_hash text, p_version text, p_lease uuid, p_title text, p_text text, p_source text,
    p_translation text, p_concepts jsonb, p_annotations jsonb
)
returns uuid
language plpgsql
set search_path = ''
as $$
declare
    owner_id uuid := auth.uid();
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

    insert into public.korean_documents
        (user_id, title, original_text, source, content_hash, analysis_version, analysis)
    values (owner_id, p_title, p_text, p_source, p_hash, p_version,
        jsonb_build_object('translation', p_translation, 'annotations', public.korean_resolve_annotations(p_concepts, p_annotations)))
    returning id into document_id;
    return document_id;
end
$$;

-- Add word glosses to the original document while retaining its existing annotations and practice.
create function public.korean_add_word_glosses(
    p_document uuid, p_lease uuid, p_concepts jsonb, p_annotations jsonb
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
    owner_id uuid := auth.uid();
    doc public.korean_documents%rowtype;
    additions jsonb;
begin
    if owner_id is null or coalesce(auth.jwt()->>'is_anonymous', 'false') <> 'false' then
        return false;
    end if;

    perform pg_advisory_xact_lock(hashtextextended(owner_id::text, 0));
    select * into doc from public.korean_documents where id = p_document and user_id = owner_id for update;
    if not found then
        return false;
    end if;

    delete from public.korean_import_claims
    where user_id = owner_id and lease = p_lease and expires_at > now()
        and content_hash = doc.content_hash and analysis_version = doc.analysis_version || ':word-glosses';
    if not found then
        return false;
    end if;

    if exists (
        select 1 from jsonb_array_elements(p_annotations) as item
        where item->>'kind' is distinct from 'word'
            or not coalesce((item->>'start')::integer >= 0
                and (item->>'end')::integer > (item->>'start')::integer
                and (item->>'end')::integer <= char_length(doc.original_text)
                and substr(doc.original_text, (item->>'start')::integer + 1,
                    (item->>'end')::integer - (item->>'start')::integer) = item->>'surface', false)
    ) then
        raise exception 'Invalid word gloss span';
    end if;

    select jsonb_agg(item.value order by item.ordinality) into additions
    from jsonb_array_elements(p_annotations) with ordinality as item
    where not exists (
        select 1 from jsonb_array_elements(doc.analysis->'annotations') as saved
        where (saved->>'start')::integer <= (item.value->>'start')::integer
            and (saved->>'end')::integer >= (item.value->>'end')::integer
    );
    if additions is not null then
        update public.korean_documents set analysis = jsonb_set(analysis, '{annotations}',
            (analysis->'annotations') || public.korean_resolve_annotations(p_concepts, additions))
        where id = p_document and user_id = owner_id;
    end if;
    return true;
end
$$;

revoke all on function public.korean_add_word_glosses(uuid, uuid, jsonb, jsonb) from public, anon, authenticated;
grant execute on function public.korean_add_word_glosses(uuid, uuid, jsonb, jsonb) to authenticated;

commit;
