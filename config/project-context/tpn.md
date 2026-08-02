# 状态感知网络、TPN：专题判断卡

TPN特指阿里云提出的Token Performance Network。检索不能局限于TPN名称，还应覆盖KVCache感知的网络与带宽调度、Prefill/Decode解耦通信、KVCache传输以及面向TTFT、TPOT和Token吞吐的网络优化。

当前重点判断：

1. 网络是否真正感知推理阶段、KVCache位置、请求优先级或Token性能目标，而不只是普通流量分类。
2. 网络侧机制是否减少KVCache跨节点传输、排队等待或热点链路拥塞。
3. 方案是否给出端到端TTFT、TPOT、Token吞吐、P95或网络利用率，而不是只报告微基准。
4. 与纯GPU内存调度、请求调度相比，网络侧机制增加了什么不可替代的能力。
