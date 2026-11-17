# APEX original offline TIFF document-renaming sample

State: researched / locally tested / review-only. This is NOT a funded customer assignment, an accepted delivery, a live deployed service, or a verified revenue source. A November 17, 2026 marketplace posting advertised a $100 document automation budget, but the job was NOT applied to and the applicant identity gate is unresolved.

## Workflow

A local Tesseract OCR executable reads TIFF files; the operator supplies a regex with exactly one capture group defining the authoritative identifier. The program previews in-place filename changes. Example:

    python examples/tiff_ocr_batch/batch_tiff_renamer.py /path/to/scans --pattern 'INVOICE:\s+([A-Z0-9-]+)' --manifest preview.csv

For dense single-block documents, optionally add `--ocr-psm 6` to either preview or apply; the default is Tesseract `--psm 3` automatic page segmentation. Compare both **dry-run** previews with the real document labels before choosing; `6` is not a universal accuracy improvement and never auto-corrects `0`/`O` or any other identifier. The CLI accepts only modes 3 and 6, and each selection is passed through to local Tesseract.\n\nAfter checking the preview and backing up inputs, add --apply --manifest executed.csv. Apply REQUIRES an exclusive new manifest: intended actions are written and fsynced BEFORE changes, then result rows are appended. A crash can leave planned-only entries: inspect actual source and destination state before any retry. Preview-only manifests retain the compact status format. No OCR text is transmitted over the network or persisted in the manifest. Symlinks, collisions, unmatched labels, unsafe names and existing targets never get silently overwritten. On the same filesystem, exclusive hardlink creation precedes unlinking the source; a partial failure may leave two copies but does not overwrite existing files. Blocked entries prevent apply.

Python code uses only the standard library; OCR requires a separately installed licensed Tesseract executable and language pack. Default safety limits are 1,000 input TIFFs and 20 seconds OCR per file. These are not throughput benchmarks.

## Evidence and boundaries

Eleven stdlib unit tests passed locally Nov 17, including manifest preflight and atomic collision failure. A synthetic end-to-end TIFF displaying "INVOICE: DEMO-2046" passed OCR, dry run, then explicit apply. No client data, buyer contact, payment, remote service, account or purchase was used. Large batches, handwriting, low-quality scans, actual buyer field grammar, support resources and privacy permission are unverified. Do not submit Upwork proposals or spend Connects while identity/approval gates remain unresolved. This is preparation, not paid-client experience.

## November 17 follow-up (review-first quality gate)

A bounded 49-file fictional-image sample using the earlier demo skipped five OCR labels because Tesseract confused the digit `0` and letter `O`. A targeted mode-6 retry recognized those five synthetics, but an attempted broader comparison timed out. This option is deliberately operator-selected, not automatic, and does not validate 1,000-file throughput, client documents or fully reliable extraction. Inspect every preview, confirm expected identifiers against the original documents, and use a new exclusive audit manifest if explicitly applying. The original reviewer-controlled/no-overwrite protections remain in force. Unit tests verify the new mode wiring, safety rejection and no-apply default; hosted validation and commercial buyer acceptance must be checked separately.
