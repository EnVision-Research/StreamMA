<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="imgs/favicon.svg">
    <img src="imgs/favicon.svg" width="72" alt="StreamMA logo">
  </picture>
  <br>
  StreamMA
</h1>

<p align="center">
  <b><i>Streaming Communication in Multi-Agent Reasoning</i></b>
</p>

<p align="center">
  <a href="https://arxiv.org/abs/2606.05158">
    <img src="https://img.shields.io/badge/Paper-arXiv-b31b1b.svg?logo=arxiv&style=flat-square" alt="arXiv"></a>
  <a href="https://zhenyangcs.github.io/StreamMA-website">
    <img src="https://img.shields.io/badge/Project-Page-2f9e6e?style=flat-square" alt="Project Page"></a>
  <a href="#citation">
    <img src="https://img.shields.io/badge/BibTeX-Cite-eaeaea?style=flat-square" alt="BibTeX"></a>
  <!--
  <a href="#">
    <img src="https://img.shields.io/badge/Zhihu-Blog-0084FF?logo=zhihu&logoColor=white&style=flat-square" alt="Zhihu"></a>
  <a href="https://www.xiaohongshu.com/discovery/item/6a20e2ae000000003700c8a5">
    <img src="https://img.shields.io/badge/RedNote-Post-FF2442?logo=xiaohongshu&logoColor=white&style=flat-square" alt="RedNote"></a>
  -->
</p>

<p align="center">
  <a href="https://zhenyangcs.github.io/"><b>Zhen&nbsp;Yang</b></a><sup>1</sup> &nbsp;·&nbsp;
  <a href="https://xuxiaogang.com/"><b>Xiaogang&nbsp;Xu</b></a><sup>3</sup> &nbsp;·&nbsp;
  <a href="https://encounter1997.github.io/"><b>Wen&nbsp;Wang</b></a><sup>3</sup> &nbsp;·&nbsp;
  <a href="https://scholar.google.com/citations?user=kwDXTpAAAAAJ&hl=en"><b>Cong&nbsp;Chen</b></a><sup>3</sup>
  <br>
  <a href="https://xander23333.github.io/index.html"><b>Xander&nbsp;Xu</b></a><sup>2&#42;</sup> &nbsp;·&nbsp;
  <a href="https://scholar.google.com/citations?user=n7j4bJUAAAAJ&hl=en"><b>Ying-Cong&nbsp;Chen</b></a><sup>1,4&#42;</sup>
  <br><br>
  <sup>1</sup>HKUST(GZ) &nbsp;·&nbsp; <sup>2</sup>Alibaba&nbsp;Group &nbsp;·&nbsp; <sup>3</sup>ZJU &nbsp;·&nbsp; <sup>4</sup>HKUST
  <br>
  <sub><sup>&#42;</sup>Co-corresponding authors</sub>
</p>

---

<!--
<h2 align="center">🏆 SimpleBench — StreamMA sets a new SOTA</h2>

<div align="center">

| Rank | Model | Score |
|:----:|:------|------:|
| 🥇 | **StreamMA**&nbsp;<sub>(GPT-5.4-medium, A4 S4)</sub> | **98.0%** |
| 1 | Gemini 3.1 Pro Preview | 79.6% |
| 2 | GPT-5.5 Pro | 76.9% |
| 3 | Gemini 3 Pro Preview | 76.4% |
| 4 | GPT-5.4 Pro | 74.1% |
| 5 | GPT-5.5 | 69.0% |

</div>

<p align="center"><sub>Source: <a href="https://epoch.ai/benchmarks/simplebench">epoch.ai/benchmarks/simplebench</a> · StreamMA evaluated on 10 public questions, 5 runs avg.</sub></p>

-->
---

<h2 align="center">📊 TL;DR</h2>

<p align="center">
  <img src="imgs/streamma_method.gif" alt="StreamMA method animation" width="960">
</p>

<table align="center">
<tr>
  <td align="center" width="33%">
    <h2>+7.3&nbsp;pp</h2>
    <b>Average accuracy gain</b><br>
    <sub>8 benchmarks · Claude Opus 4.6<br>peak <b>+22.4 pp</b> on HMMT 2026</sub>
  </td>
  <td align="center" width="33%">
    <h2>26.9×</h2>
    <b>Wall-clock speedup</b><br>
    <sub>A=64, S=64<br>83% of theoretical bound</sub>
  </td>
  <td align="center" width="34%">
    <h2>½ cost</h2>
    <b>Stream×4 beats Serial×16</b><br>
    <sub>$2.75 vs $5.46<br>higher accuracy at half the price</sub>
  </td>
</tr>
</table>

---

<h2 align="center">⚡ Quick Start</h2>

```bash
pip install openai
python StreamMA.py
```

<p align="center">Or in your own script:</p>

```python
import asyncio
from StreamMA import (
    StreamMA, RunLogger,
    PROMPT_A_CHAIN, PROMPT_B_CHAIN, PROMPT_C_CHAIN,
)

config = {
    "Agent_A": {"system_prompt": PROMPT_A_CHAIN, "next": ["Agent_B"]},
    "Agent_B": {"system_prompt": PROMPT_B_CHAIN, "next": ["Agent_C"]},
    "Agent_C": {"system_prompt": PROMPT_C_CHAIN},
}

async def main():
    logger = RunLogger(input="***", logger_path="logger.json")
    logger.start()
    await StreamMA.run(
        config, "your problem here",
        api_key="***", base_url="***", model="***",
        logger=logger,
    )
    logger.finish(config)

asyncio.run(main())
```

---

<h2 align="center">🔧 Customising the topology</h2>

<p align="center">The DAG is fully driven by the <code>config</code> dict — change the topology by editing each agent's <code>next: [...]</code>, and pair every agent with its own <code>system_prompt</code>:</p>

```python
# Chain   A → B → C
{"A": {..., "next": ["B"]}, "B": {..., "next": ["C"]}, "C": {...}}

# Tree    A → {B, C}
{"A": {..., "next": ["B", "C"]}, "B": {...}, "C": {...}}

# Graph   A → B → C, with shortcut A → C
{"A": {..., "next": ["B", "C"]}, "B": {..., "next": ["C"]}, "C": {...}}
```

<p align="center">
💡 <b>Random sample speedups</b> observed across topologies on HMMT 2026:<br>
<b>Graph 1.92×</b> &nbsp;·&nbsp; <b>Chain 1.84×</b> &nbsp;·&nbsp; <b>Tree 1.82×</b>
</p>

---

<h2 align="center">📈 Logger output</h2>

<p align="center"><code>RunLogger</code> records per-agent token counts, KV-cache hits, API time, and an ASCII timeline of streaming segments:</p>

<details>
<summary>Click to expand example</summary>

```json
{
  "summary": {
    "agents": {
      "Agent_A": {"segments": 1, "prefill_tokens": 190,   "cached_tokens": 0,     "kv_cache_hit_ratio": 0.0,    "decode_tokens": 4084,  "api_time": 123.30},
      "Agent_B": {"segments": 4, "prefill_tokens": 30373, "cached_tokens": 10624, "kv_cache_hit_ratio": 0.3498, "decode_tokens": 10175, "api_time": 308.74},
      "Agent_C": {"segments": 4, "prefill_tokens": 42755, "cached_tokens": 23040, "kv_cache_hit_ratio": 0.5389, "decode_tokens": 7197,  "api_time": 221.08}
    },
    "agent_count": 3,
    "total_prefill_tokens": 73318,
    "total_cached_tokens":  33664,
    "total_decode_tokens":  21456,
    "total_tokens":         94774,
    "speedup_analysis": {
      "api_time": 653.12,
      "wall_time": 376.02,
      "speedup": 1.74,
      "total_kv_cache_hit_ratio": 0.4592,
      "critical_path_time": 653.12,
      "streaming_speedup": 1.74,
      "timeline": [
        "[Timeline]",
        "  Agent Agent_A:█████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 123.3s",
        "  Agent Agent_B:░░░░░███████████████████████████████████████████████░░░ 308.7s",
        "  Agent Agent_C:░░░░░░░░░░░░░████████████░░░░░░███████████████████ 221.1s",
        "            ──────────────────────────────────────────────────",
        "            │    │       │  │       │      │      │   │   │  │          ",
        "            0.0s 40.0s   98.0s      183.7s 240.6s 288.6s  353.1s        ",
        "",
        "  Legend: █ = processing, ░ = idle"
      ]
    }
  }
}
```
</details>

---

<h2 align="center">📚 Citation</h2>

<a id="citation"></a>

<p align="center">If you find StreamMA useful, please cite:</p>

```bibtex
@article{yang2026streamma,
  title={StreamMA: Streaming Communication in Multi-Agent Reasoning},
  author={Yang, Zhen and Xu, Xiaogang and Wang, Wen and Chen, Cong and Xu, Xander and Chen, Ying-Cong},
  journal={arXiv preprint arXiv:2606.05158},
  year={2026}
}
```
