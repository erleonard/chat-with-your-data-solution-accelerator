---
title: Document synthesis, export, and infographics
description: Upload large documents, restrict answers to selected files, synthesize project documentation, export it, and render grounded infographics.
ms.topic: how-to
---

[Back to *Chat with your data* README](../README.md)

# Document synthesis, export, and infographics

Use these features to turn a set of long documents, such as 100+ page PDF or Word files, into grounded project documentation and visuals.

## Upload large documents

The admin upload accepts files up to `AZURE_UPLOAD_MAX_BYTES` each. The default is 209715200 bytes (200 MiB). Upload as many files as you need; each one is parsed, chunked, and indexed independently. For more on the pipeline, see [Document ingestion](document_ingestion.md).

## Restrict answers to specific documents

Every answer is grounded in indexed content only. A fixed guardrail tells the model to use only retrieved passages, never its own knowledge. When nothing relevant is retrieved, it replies "The requested information is not available in the retrieved data."

To narrow this further, use the **Limit answers to documents** picker next to the chat box (it reads "All documents" by default) and select one or more files. Chat retrieval then searches only those files, and the selection is sent as `document_sources` on `POST /api/conversation`. Clear the selection to search the whole index again.

## Synthesize project documentation

Regular chat retrieves only the top-matching passages, so it can't summarize an entire 100-page file. Instead, select documents and choose **Synthesize project documentation** (`POST /api/synthesize`, `format: "project_documentation"`). The backend then:

1. Reads every chunk of every selected document in page order.
2. Summarizes the chunks in batches (map). Each note keeps its `[docN]` citation markers.
3. Merges the notes into one Markdown document (reduce), with sections such as overview, scope, requirements, timeline, risks, and open questions.

Progress appears in the reasoning panel. The result is saved to chat history like any other answer.

| Setting | Default | Purpose |
|---|---|---|
| `AZURE_OPENAI_SYNTHESIS_MAX_TOKENS` | `4000` | Output-token ceiling for each map and reduce call. |
| `AZURE_OPENAI_SYNTHESIS_BATCH_CHARS` | `24000` | Characters of source text summarized per map call. Lower it if you hit model context or rate limits. |

## Export

Each finished answer has **Markdown** and **Word** buttons. Exports renumber citations as `[1]`, `[2]`, and so on, and append a **Sources** section. Markdown downloads are generated in the browser. Word downloads are rendered by `POST /api/export/docx`.

## Infographics

### Grounded diagram infographic

Select documents and choose **Create infographic** (`format: "infographic"`). The synthesis returns a one-page visual summary: key figures, a mind map or flowchart, a timeline, and an optional pie chart. Diagrams are written as Mermaid and rendered in the chat as SVG (strict security level). Every figure in a diagram is also stated, with citations, in the accompanying text.

### AI-generated image (optional)

Finished answers also have an **AI image** button. The chat model first rewrites the answer as a visual brief using only facts from that answer. A gpt-image deployment then draws it, and the result is labeled as AI-generated with a PNG download. Image models can misspell or distort text, so check the image against the cited answer before sharing it.

This feature is off by default. To enable it:

```bash
azd env set AZURE_IMAGE_MODEL_NAME gpt-image-1
azd up
```

This deploys the model and sets `AZURE_OPENAI_IMAGE_DEPLOYMENT` on the backend. When the variable is empty, `POST /api/infographic/image` returns `503`. gpt-image is available only in some regions and may require access approval. Check availability in your `AZURE_AI_SERVICE_LOCATION` before enabling it.

## Related documentation

* [Demo runbook: from 100+ page documents to project documentation](demo_runbook_project_documentation.md)
* [Supported file types](supported_file_types.md)
* [Document ingestion](document_ingestion.md)
* [Customizing azd parameters](customizing_azd_parameters.md)
