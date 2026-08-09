# Balanced Evidence Pack

This first read intentionally spans problem context, mechanism, evaluation/results, and limitations. Evidence locators preserve the source section names.

## Evidence locator: SLIM: Saturation-Aware Lightweight Performance Modeling for LLM Serving

# SLIM: Saturation-Aware Lightweight Performance Modeling for LLM Serving

Source: https://arxiv.org/abs/2607.29575v1

## Evidence locator: Available summary

## Available summary

Large language model (LLM) serving commonly increases batch size to improve throughput, but performance eventually reaches a deployment-dependent plateau beyond which larger batches provide marginal gains while increasing latency and GPU memory consumption. Previous studies have attributed this behavior to HBM/DRAM bandwidth limitations, but the underlying causes have primarily been supported by conceptual arguments or high-level performance observations. As our first contribution, we present a detailed GPU characterization using hardware profiling techniques, demonstrating that throughput saturation originates in the attention kernels during the decode phase. Specifically, we show that their nearly constant arithmetic intensity as active-context lengths increases -not merely larger batch sizes- drives DRAM-bandwidth saturation, while the achieved compute throughput remains far below the hardware limit. Building on this analysis, we present the Batching Configuration Advisor (BCA), which selects the highest-throughput batching configuration satisfying a target latency constraint and identifies up to 55 GB of GPU memory allocation that can be avoided for the evaluated OPT models with minimal throughput loss. To enable these recommendations, we introduce SLIM (Saturation-Aware Lightweight Performance Model), a semi-analytical model that predicts LLM inference throughput and latency from analytical formulations of Transformer computation and memory traffic. Across the evaluated scenarios, SLIM outperforms representative performance-modeling baselines while successfully generalizing to previously unseen operating conditions.