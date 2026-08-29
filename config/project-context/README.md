# Project context cards

These Markdown files are runtime inputs. They connect each configured topic to current project questions, evidence preferences, decision criteria, and known boundaries.

Relevance, fact extraction, Reader Projection, and issue synthesis may receive one of these files through a task input. Agents must read only the card named by the task. Facts from a source and internal project judgements must remain distinguishable.

Topic-to-file routing is defined in `briefing_skill/config.py`. Add a context card and update that mapping when a new topic requires project-specific judgement. Changing a card can invalidate relevance or facts cache reuse because evaluator and extractor versions include the exposed context.
