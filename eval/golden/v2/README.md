# Golden Corpus v2

Golden v2 expands from smoke tests to topic coverage.

Current coverage:

- AI network: TPN, KVCache scheduling, RDMA/WAN
- Memory semantics: DSA, CXL, disaggregated memory
- DPU offload: TLS, compression, EC, metadata
- Agent systems: code navigation, tool acceleration, cache
- Cross-domain inference: KVCache transfer and coherence
- Optical networking
- AI accelerators: HBM, chiplet, interconnect
- Storage and media: S3, metadata, HBF, KV systems

A case should include semantic relations rather than only keywords:

```yaml
mechanism: what changed
causal_chain: why it improves performance
boundary: when it works
forbidden_claims: common misinterpretations
```

Keyword checks remain only regression guards for explicit facts.
