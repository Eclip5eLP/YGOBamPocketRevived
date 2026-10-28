Project: interoperability/preservation research. Revive the backend of a shut-down
mobile game (Yu-Gi-Oh! BAM Pocket, package air.com.konami.ygo, Adobe AIR / AS3,
client v1.11.2) so the unmodified-logic client can fetch its assets and run without root.

Rules:
- Never modify input/. Copy to work/.
- Every claim about the protocol must cite a file path plus class/method or line.
  Label each finding VERIFIED (seen in code or data) or INFERRED. If unknown, write
  "unknown". Do not guess field names, endpoints or crypto parameters.
- Don't read huge files whole. Use ripgrep and targeted reads.
- Append findings to notes/findings.md as you go.
- Ask before any network access or software install.