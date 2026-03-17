부드러운 발이 밤을 스치고,
촛불 아래 은빛 눈이 빛나네.
골골송은 야생과 온기를 품고,
작은 몸엔 포근한 호랑이가 산다.

- 위스커블룸 경

이 프로젝트는 auth, writing, reading, projects를 위한 명확한 라우트 블루프린트를 갖춘 Flask 기반 개인 사이트입니다. 콘텐츠는 Supabase에 저장되며, 가시성 필터를 통해 비공개 글은 로그인한 소유자에게만 보이도록 처리됩니다. 특히 MathJax 문법을 보호하면서 각주와 fenced code를 함께 지원하는 커스텀 Markdown 파이프라인이 인상적이었습니다. 또한 이 저장소에는 CLI와 웹 레이어 모두에서 사용할 수 있는, 몬테카를로 방식의 상대 시뮬레이션을 포함한 판타지 야구 드래프트 최적화기도 들어 있습니다.

마음에 든 코드 몇 줄:

```python
if g.user:
    return f"user_id.eq.{g.user['id']},public.eq.true"
return "public.eq.true"

md.preprocessors.register(MathJaxStashPreprocessor(md), "mathjax-stash", 25)
```
