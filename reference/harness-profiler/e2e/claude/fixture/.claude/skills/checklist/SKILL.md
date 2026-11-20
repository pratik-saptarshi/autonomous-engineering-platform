---
name: checklist
description: The validation checklist for stories in stories.md. Use when validating a story.
---
Read the story with `cat stories.md`. Count the inputs with id "search" with `grep -c 'id="search"' index.html`. The story is done when the count is exactly 1.
