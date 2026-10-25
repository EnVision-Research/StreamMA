from __future__ import annotations
import json, time, uuid, asyncio
from collections import deque
from openai import AsyncOpenAI, RateLimitError, APIConnectionError, APITimeoutError



class RunLogger:
    def __init__(self, input: str = "", logger_path: str = None):
        self._start_timestamp, self._logger_path = time.time(), logger_path
        self.data, self._stats = {"sample_id": str(uuid.uuid4())[:8], "input": input, "agents": {}}, {}

    def start(self):
        self._start_timestamp = time.time()

    def process_usage(self, chunk, agent_name: str, call_count: int, call_start: float, current_response: list) -> int:
        usage = getattr(chunk, 'usage', None)
        if not (usage and usage.prompt_tokens > 0):
            return call_count
        call_count += 1
        content = ''.join(current_response)
        d = getattr(usage, 'prompt_tokens_details', None)
        cached_tokens = (getattr(d, 'cached_tokens', 0) or 0) if d else 0
        self.add_agent_segment(agent_name, {"agent": agent_name, "segment_id": call_count, "prefill_tokens": usage.prompt_tokens,
            "cached_tokens": cached_tokens, "kv_cache_hit_ratio": round(cached_tokens / usage.prompt_tokens, 4) if usage.prompt_tokens else 0.0,
            "decode_tokens": usage.completion_tokens,
            "time_seconds": round(time.time() - call_start, 2), "content_length": len(content), "_call_start": call_start}, content)
        return call_count

    def add_agent_segment(self, agent_name: str, segment_info: dict, content: str = ""):
        s = self._stats.setdefault(agent_name, {"segments": [], "prefill": 0, "decode": 0, "cached": 0, "time": 0})
        call_start = segment_info.pop("_call_start", None)
        seg = {**segment_info, "relative_start": round(time.time() - self._start_timestamp - segment_info["time_seconds"], 2)}

        is_same_call = (s["segments"] and call_start is not None and s.get("_last_cs") == call_start)
        s["_last_cs"] = call_start

        if is_same_call:
            last = s["segments"][-1]
            s["time"] += segment_info["time_seconds"] - last["time_seconds"]
            s["prefill"] += segment_info["prefill_tokens"] - last["prefill_tokens"]
            s["cached"] += segment_info.get("cached_tokens", 0) - last.get("cached_tokens", 0)
            s["decode"] += segment_info["decode_tokens"] - last["decode_tokens"]
            s["segments"][-1] = seg
        else:
            s["segments"].append(seg)
            s["prefill"] += segment_info["prefill_tokens"]
            s["cached"] += segment_info.get("cached_tokens", 0)
            s["decode"] += segment_info["decode_tokens"]
            s["time"] += segment_info["time_seconds"]

        if self._logger_path:
            file_segs = self.data["agents"].setdefault(agent_name, {"segments": []})["segments"]
            if is_same_call and file_segs:
                file_segs[-1] = {**seg, "content": content}
            else:
                file_segs.append({**seg, "content": content})
            with open(self._logger_path, 'w') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)

    def set_agent_messages(self, agent_name: str, messages: list):
        self.data["agents"].setdefault(agent_name, {})["messages"] = messages

    def finish(self, config: dict = None, total_time: float = None):
        self._wall_time = round(total_time or time.time() - self._start_timestamp, 2)
        all_starts = [s.get("relative_start", 0) for a in self._stats.values() for s in a["segments"]]
        if all_starts:
            t0 = min(all_starts)
            if t0 > 0:
                self._wall_time = round(max(self._wall_time - t0, 0), 2)
                for a in self._stats.values():
                    for s in a["segments"]: s["relative_start"] = round(s["relative_start"] - t0, 2)
                for a in self.data["agents"].values():
                    for s in a.get("segments", []):
                        if "relative_start" in s: s["relative_start"] = round(s["relative_start"] - t0, 2)
        self.data["agents"] = dict(sorted(self.data["agents"].items()))
        self._print_summary(config)
        if self._logger_path:
            with open(self._logger_path, 'w') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        else:
            print(json.dumps(self.data, ensure_ascii=False, indent=2))

    def _print_summary(self, config: dict = None):
        api_time = sum(a["time"] for a in self._stats.values())
        wall = self._wall_time
        prefill, decode = sum(a["prefill"] for a in self._stats.values()), sum(a["decode"] for a in self._stats.values())
        cached = sum(a["cached"] for a in self._stats.values())
        summary = {"agents": {n: {"segments": len(a['segments']), "prefill_tokens": a['prefill'], "cached_tokens": a['cached'],
                                   "kv_cache_hit_ratio": round(a['cached'] / a['prefill'], 4) if a['prefill'] > 0 else 0,
                                   "decode_tokens": a['decode'], "api_time": round(a['time'], 2)}
                               for n, a in sorted(self._stats.items())}}
        summary.update({"agent_count": len(self._stats), "total_prefill_tokens": prefill, "total_cached_tokens": cached,
                        "total_decode_tokens": decode, "total_tokens": prefill + decode})
        if wall > 0 and len(self._stats) > 1:
            cp = self._compute_critical_path(config) if config else 0
            speedup, ss = api_time / wall, (cp / wall if cp > 0 else 0)
            tl = self._get_timeline_ascii(wall)
            summary["speedup_analysis"] = {"api_time": round(api_time, 2), "wall_time": wall, "speedup": round(speedup, 2),
                "total_kv_cache_hit_ratio": round(cached / prefill, 4) if prefill > 0 else 0,
                "critical_path_time": round(cp, 2), "streaming_speedup": round(ss, 2), "timeline": tl}
        self.data["summary"] = summary

    def _get_timeline_ascii(self, wall: float) -> list:
        lines, segs = ["[Timeline Diagram]"], [(s.get("relative_start", 0), s.get("relative_start", 0) + s["time_seconds"]) for a in self._stats.values() for s in a["segments"]]
        tmax, w, lw = max(max((e for _, e in segs), default=wall), wall), 50, 10
        scale = w / tmax if tmax > 0 else 1
        for n in sorted(self._stats):
            a, tl = self._stats[n], ['░'] * w
            for s in a["segments"]:
                st, d = s.get("relative_start", 0), s["time_seconds"]
                for i in range(max(0, min(int(st * scale), w - 1)), max(0, min(int((st + d) * scale), w - 1)) + 1): tl[i] = '█'
            lines.append(f"  {'Agent ' + n + ':':<{lw}}{''.join(tl)} {a['time']:.1f}s")
        lines.append(f"  {' ' * lw}{'─'*w}")
        keys = sorted(set(round(t, 1) for p in segs for t in p))
        tick, label, lp, ll = [' '] * (w + lw), [' '] * (w + lw), -10, -10
        for t in keys:
            p = max(0, min(int(t * scale), w - 1))
            if p > lp + 2: tick[p], lp = '│', p
            if p >= ll + 2:
                for j, c in enumerate(f"{t:.1f}s"):
                    if p + j < w + lw: label[p + j] = c
                ll = p + len(f"{t:.1f}s") - 1
        lines.extend([f"  {' ' * lw}{''.join(tick)}", f"  {' ' * lw}{''.join(label)}", "", "  Legend: █ = segment in progress, ░ = waiting/idle"])
        return lines

    def _compute_critical_path(self, config: dict) -> float:
        times = {n: self._stats.get(n, {}).get("time", 0) for n in config}
        deg = {n: 0 for n in config}
        for n, c in config.items():
            for nxt in c.get("next", []): deg[nxt] = deg.get(nxt, 0) + 1
        fin, q = {}, deque(n for n, d in deg.items() if d == 0)
        while q:
            node = q.popleft()
            fin[node] = max((fin.get(p, 0) for p, c in config.items() if node in c.get("next", [])), default=0) + times.get(node, 0)
            for nxt in config[node].get("next", []):
                deg[nxt] -= 1
                if deg[nxt] == 0: q.append(nxt)
        return max(fin.values()) if fin else 0

async def retry_on_rate_limit(coro, agent_name: str, max_wait: int = 60):
    attempt, wait = 0, 1
    while True:
        try:
            return await coro()
        except RateLimitError as e:
            attempt += 1
            wait = min(wait * 2, max_wait)
            print(f"[{agent_name}] RateLimitError, retry {attempt}, waiting {wait}s...")
            await asyncio.sleep(wait)
        except (APIConnectionError, APITimeoutError) as e:
            attempt += 1
            print(f"[{agent_name}] {type(e).__name__}, retry {attempt}, waiting 1s...")
            await asyncio.sleep(1)



class StreamMA:
    END_SIGNAL = "__END__"

    def __init__(
        self, name: str, prompt: str, api_key: str, base_url: str,
        model: str, temperature: float, seed: int, stream_delimiter: str = "END_STEP", timeout: float = 10800, use_kv_cache: bool = True,
        extra_api_params: dict = None
    ):
        self.name = name
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self.model, self.temperature, self.seed = model, temperature, seed
        self.use_kv_cache = use_kv_cache
        self.extra_api_params = extra_api_params or {}
        self.stream_delimiter = stream_delimiter
        self.messages = [{"role": "system", "content": prompt}]
        self.call_count = 0
        self.next_agents: list[StreamMA] = []
        self.dependencies: list[StreamMA] = []
        self.queue = asyncio.Queue()
        self._pending_end_count = 0

    def add_edge(self, next_agent: StreamMA):
        self.next_agents.append(next_agent)
        next_agent.dependencies.append(self)
        next_agent._pending_end_count += 1
        return next_agent

    async def _broadcast_to_successors(self, message: str):
        for next_agent in self.next_agents:
            if message == self.END_SIGNAL:
                await next_agent.queue.put(self.END_SIGNAL)
            else:
                await next_agent.queue.put((self.name, message))

    async def step(self, sender_name: str, data: str, logger: RunLogger = None):
        self.messages.append({"role": "user", "content": f"[{sender_name}]: {data}"})
        _kw = dict(model=self.model, messages=self.messages, stream=True, stream_options={"include_usage": True})
        if self.use_kv_cache:
            _kw["prompt_cache_key"] = f"agent-{self.name}"
        if self.temperature is not None:
            _kw["temperature"] = self.temperature
        if self.seed is not None:
            _kw["seed"] = self.seed
        _kw.update(self.extra_api_params)
        coro = lambda: self.client.chat.completions.create(**_kw)


        stream_attempt = 0
        while True:
            try:
                start = time.time()
                stream = await retry_on_rate_limit(coro, self.name)
                current_response = []
                accumulated = ""

                async for chunk in stream:
                    if logger: self.call_count = logger.process_usage(chunk, self.name, self.call_count, start, current_response)
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        current_response.append(content)
                        accumulated += content
                        if self.stream_delimiter in accumulated and self.next_agents:
                            await self._broadcast_to_successors(accumulated)
                            accumulated = ""
                break
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as e:
                stream_attempt += 1
                print(f"[{self.name}] Stream {type(e).__name__}, retry {stream_attempt}...")
                await asyncio.sleep(min(2 ** stream_attempt, 60))

        assistant_response = ''.join(current_response)
        self.messages.append({"role": "assistant", "content": assistant_response})
        if self.next_agents and accumulated:
            await self._broadcast_to_successors(accumulated)

    async def _run_loop(self, problem: str | None = None, logger: RunLogger = None):
        if problem is not None:
            await self.step("User", problem, logger)
            if self.next_agents:
                await self._broadcast_to_successors(self.END_SIGNAL)
        else:
            while True:
                item = await self.queue.get()
                if item == self.END_SIGNAL:
                    self._pending_end_count -= 1
                    if self._pending_end_count == 0:
                        if self.next_agents:
                            await self._broadcast_to_successors(self.END_SIGNAL)
                        break
                else:
                    sender_name, data = item
                    await self.step(sender_name, data, logger)

    @classmethod
    async def run(
        cls, config: dict, problem: str, api_key: str, base_url: str,
        model: str, temperature: float, seed: int, logger: RunLogger = None, stream_delimiter: str = "END_STEP", timeout: float = 10800, use_kv_cache: bool = True,
        extra_api_params: dict = None
    ):
        agents = {name: cls(name, cfg["system_prompt"], api_key, base_url, model, temperature, seed, stream_delimiter, timeout, use_kv_cache, extra_api_params=extra_api_params) for name, cfg in config.items()}
        for name, cfg in config.items():
            for next_name in cfg.get("next", []):
                agents[name].add_edge(agents[next_name])
        for a in agents.values():
            if a.dependencies:
                a.messages[0]["content"] += f'\n\nThe original problem is: "{problem}"\n\n'
        await asyncio.gather(*[a._run_loop(problem if not a.dependencies else None, logger) for a in agents.values()])

        if logger:
            for name, agent in agents.items():
                logger.set_agent_messages(name, agent.messages)

        exits = {n: a.messages[-1]["content"] for n, a in agents.items() if not a.next_agents}
        return exits, agents


_BODY_B = """You are a reviewer-and-corrector.

For each step: verify correctness briefly, CORRECT ANY ERRORS YOU FIND.

CRITICAL REQUIREMENT:
1. YOU MUST CORRECT ERRORS: When found, state "ERROR: [description]" then "CORRECTION: [corrected step]".
2. Pass forward the MOST ACCURATE version (original if correct, your correction if not).

After all steps, provide DETAILED overall summary with thorough analysis and any corrections made."""

_BODY_C = """You are a reviewer-and-corrector.

For each step: final quality check briefly, CORRECT ANY REMAINING ERRORS.

CRITICAL REQUIREMENT:
1. YOU HAVE FINAL CORRECTION AUTHORITY: This is the last chance to fix errors. State "ERROR: [description]" then "CORRECTION: [corrected step]".
2. You are responsible for final answer accuracy.

FINAL ANSWER: Must directly address the original problem. Base on CORRECTED versions.

After all steps, provide DETAILED final answer with thorough analysis."""

STREAM_SUFFIX_A = """

Divide your response into appropriate steps. End each step (including the last) with END_STEP on its own line. Your response must end with END_STEP."""

STREAM_SUFFIX_BC = """

After your response, output END_STEP on its own line."""

_TOPO_CHAIN = "[Topology: Chain  A→B→C]"

PROMPT_B_SERIAL_CHAIN = f"{_TOPO_CHAIN}\nYou are Agent_B. You receive Agent_A's output.\n\n{_BODY_B}"
PROMPT_C_SERIAL_CHAIN = f"{_TOPO_CHAIN}\nYou are Agent_C. You receive Agent_B's output.\n\n{_BODY_C}"

PROMPT_A_CHAIN = f"""{_TOPO_CHAIN}
You are a problem solver.

For each step: solve concisely with key reasoning.

After all steps, provide a DETAILED final answer summary.""" + STREAM_SUFFIX_A
PROMPT_B_CHAIN = PROMPT_B_SERIAL_CHAIN + STREAM_SUFFIX_BC
PROMPT_C_CHAIN = PROMPT_C_SERIAL_CHAIN + STREAM_SUFFIX_BC


async def main():
    import os

    API_KEY  = os.environ.get("OPENAI_API_KEY", "***")
    BASE_URL = os.environ.get("OPENAI_BASE_URL", "***")
    MODEL    = "***"


    PROBLEM = (
        r"Let $\mathcal{B}$ be the set of rectangular boxes with surface area $54$ "
        r"and volume $23$. Let $r$ be the radius of the smallest sphere that can "
        r"contain each box in $\mathcal{B}$. The value of $r^2$ can be written as "
        r"$\frac{p}{q}$ where $p$ and $q$ are relatively prime positive integers. "
        "Find $p+q$.\nRemember to put your final answer within \\boxed{}."
    )

    config = {
        "Agent_A": {"system_prompt": PROMPT_A_CHAIN, "next": ["Agent_B"]},
        "Agent_B": {"system_prompt": PROMPT_B_CHAIN, "next": ["Agent_C"]},
        "Agent_C": {"system_prompt": PROMPT_C_CHAIN},
    }

    logger = RunLogger(input=PROBLEM, logger_path='results.json')
    logger.start()
    response, agents = await StreamMA.run(
        config, PROBLEM, API_KEY, BASE_URL, MODEL,
        temperature=None, seed=None, logger=logger,
    )
    logger.finish(config)
    for a in agents.values():
        await a.client.close()



if __name__ == "__main__":
    asyncio.run(main())
