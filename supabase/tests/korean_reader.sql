-- Run on a disposable or local Supabase database after the reader migration.
begin;

insert into auth.users (id) values
    ('00000000-0000-0000-0000-000000000001'),
    ('00000000-0000-0000-0000-000000000002');

set local role anon;
do $$
begin
    begin
        perform 1 from public.korean_documents;
        raise exception 'Anonymous read was allowed';
    exception when insufficient_privilege then null;
    end;
    begin
        perform public.korean_claim_import('hash', '1', gen_random_uuid());
        raise exception 'Anonymous RPC was allowed';
    exception when insufficient_privilege then null;
    end;
end
$$;

set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000001', true);
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-000000000001","is_anonymous":false}', true);

do $$
declare
    lease_id uuid := gen_random_uuid();
    doc_id uuid;
    second_doc_id uuid;
    target_id uuid;
    practice_id uuid;
    annotations jsonb := '[{"start":0,"end":4,"surface":"말하려고","concept_refs":[0]}]';
    concepts jsonb := '[{"key":"construction:-(으)려고하다:intention","alias_keys":["construction:-려고하다:intention"],
        "kind":"construction","form":"-(으)려고 하다","sense":"intention","meaning":"intend to"}]';
    alias_concepts jsonb := '[{"key":"construction:-려고하다:intention","alias_keys":[],
        "kind":"construction","form":"-려고 하다","sense":"intention","meaning":"intend to"}]';
    word_glosses jsonb := '[{"start":5,"end":7,"kind":"word","surface":"했어","concept_refs":[0]}]';
begin
    if not public.korean_claim_import('hash', '1', lease_id)
        or public.korean_claim_import('hash', '1', gen_random_uuid()) then
        raise exception 'Import lease did not deduplicate';
    end if;
    if public.korean_save_document('hash', '1', gen_random_uuid(), 'Title', '말하려고', null,
            'Intend to tell', concepts, annotations) is not null then
        raise exception 'Import finalized with the wrong lease';
    end if;

    doc_id := public.korean_save_document('hash', '1', lease_id, 'Title', '말하려고 했어', null,
        'Intend to tell', concepts, annotations);
    if doc_id is null or public.korean_claim_import('hash', '1', lease_id) then
        raise exception 'Saved analysis was not reused';
    end if;
    perform public.korean_claim_import('second', '1', lease_id);
    second_doc_id := public.korean_save_document('second', '1', lease_id, 'Title', '말하려고', null,
        'Intend to tell', alias_concepts, annotations);
    select (analysis#>>'{annotations,0,concept_ids,0}')::uuid into target_id
        from public.korean_documents where id = doc_id;
    if target_id is null or (select count(*) from public.korean_concepts) <> 1
        or (select (analysis#>>'{annotations,0,concept_ids,0}')::uuid
            from public.korean_documents where id = second_doc_id) is distinct from target_id then
        raise exception 'Canonical concept was not reused';
    end if;

    insert into public.korean_user_knowledge (concept_id, recognition_state) values (target_id, 'known');
    insert into public.korean_practice_sessions (document_id, exercises)
        select doc_id, jsonb_agg(jsonb_build_object('concept_ids', jsonb_build_array(target_id)))
        from generate_series(1,5) returning id into practice_id;
    if not public.korean_record_attempt(practice_id, 0, '가려고 했어요.', '{"correct":false}')
        or public.korean_record_attempt(practice_id, 0, '다시 했어요.', '{"correct":true}') then
        raise exception 'Attempt could not be recorded idempotently';
    end if;
    if not exists (select 1 from public.korean_user_knowledge where concept_id = target_id
        and recognition_state = 'known' and production_state = 'needs_practice') then
        raise exception 'Production update overwrote explicit recognition';
    end if;
    insert into public.korean_user_knowledge (user_id, concept_id, recognition_state)
        values (auth.uid(), target_id, 'learning') on conflict (user_id, concept_id)
        do update set recognition_state = excluded.recognition_state;
    if not exists (select 1 from public.korean_user_knowledge where concept_id = target_id
        and recognition_state = 'learning' and production_state = 'needs_practice') then
        raise exception 'Recognition update overwrote practice history';
    end if;

    if not public.korean_claim_import('hash', '1:word-glosses', lease_id) then
        raise exception 'Could not claim a word-gloss update';
    end if;
    if public.korean_add_word_glosses(doc_id, gen_random_uuid(), concepts, word_glosses)
        or not public.korean_add_word_glosses(doc_id, lease_id, concepts, word_glosses) then
        raise exception 'Word gloss updates did not require the matching lease';
    end if;
    if not exists (select 1 from public.korean_documents where id = doc_id
        and analysis->>'translation' = 'Intend to tell'
        and jsonb_array_length(analysis->'annotations') = 2
        and analysis#>>'{annotations,1,concept_ids,0}' = target_id::text)
        or not exists (select 1 from public.korean_exercise_attempts where session_id = practice_id) then
        raise exception 'Word gloss update lost existing analysis or practice';
    end if;

    perform set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000002', true);
    perform set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-000000000002"}', true);
    if exists (select 1 from public.korean_documents) or exists (select 1 from public.korean_concepts)
        or exists (select 1 from public.korean_user_knowledge) or exists (select 1 from public.korean_practice_sessions)
        or exists (select 1 from public.korean_exercise_attempts) then
        raise exception 'Another account could read private data';
    end if;
    delete from public.korean_documents where id = doc_id;
    if found or public.korean_record_attempt(practice_id, 1, '가려고 했어요.', '{"correct":true}') then
        raise exception 'Another account could write private data';
    end if;
    if public.korean_add_word_glosses(doc_id, lease_id, concepts, word_glosses) then
        raise exception 'Another account could add word glosses to the passage';
    end if;
    begin
        insert into public.korean_user_knowledge (user_id, concept_id, recognition_state)
            values ('00000000-0000-0000-0000-000000000001', target_id, 'learning');
        raise exception 'Explicit foreign user ID could write knowledge';
    exception when insufficient_privilege then null;
    end;

    perform set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000001', true);
    perform set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-000000000001","is_anonymous":true}', true);
    if exists (select 1 from public.korean_documents) then
        raise exception 'Anonymous Supabase account could read reader data';
    end if;

    perform set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-000000000001","is_anonymous":false}', true);
    delete from public.korean_documents where id = doc_id;
    if not found or exists (select 1 from public.korean_practice_sessions where id = practice_id)
        or exists (select 1 from public.korean_exercise_attempts where session_id = practice_id)
        or not exists (select 1 from public.korean_user_knowledge where concept_id = target_id) then
        raise exception 'Deleting a passage did not retain knowledge or cascade practice';
    end if;
end
$$;

rollback;
