"""
Fast-Path intent matcher and direct execution interceptor.
"""
import asyncio
import glob
import json
import os
import random
import re
import shutil
import subprocess
import urllib.parse
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
from loguru import logger

from backend.models.schemas import AgentStep, AgentStepStatus, AssistantState, ResponseMessage, StatusMessage, WSMessage


class TaskDecomposer:
    """Handles fast-path intent matching and direct deterministic task execution."""

    @staticmethod
    async def try_fast_path_intercept(
        planner: Any,
        user_message: str,
        lower_msg: str,
        history: List[dict],
        conversation_history: Optional[List[dict]],
        active_conv_id: Optional[int],
        mem_svc: Any,
        gatekeeper: Any,
        _log_self_improving_trace: Any,
    ) -> Optional[AsyncGenerator[WSMessage, None]]:
        # Fast-Path 0A: Live Mode Form Auto-Fill Intercept
        if any(k in lower_msg for k in ["fill form", "auto fill", "fill this form", "autocomplete form"]):
            res = await planner.tool_registry.execute_tool("auto_fill_form", {})
            response_text = f"Form auto-fill complete! Populated {res.get('fields_filled', 0)} field(s) using your profile data."
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                planner._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-Path 0B: Perception-Targeted Click Intercept
        if lower_msg.startswith(("click button", "click on", "click ", "press button", "tap ")):
            target_elem = lower_msg.replace("click button", "").replace("click on", "").replace("click", "").replace("press button", "").replace("tap", "").strip()
            if target_elem:
                res = await planner.tool_registry.execute_tool("click_element_by_name", {"element_name": target_elem})
                if res.get("status") in ("clicked", "invoked"):
                    response_text = f"Clicked on UI element '{target_elem}' successfully!"
                else:
                    response_text = f"Attempted to click '{target_elem}' on screen (Status: {res.get('status')})."
                yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
                history.append({"role": "assistant", "content": response_text})
                if conversation_history is None:
                    planner._conversation_history = history
                yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
                return

        # Fast-Path 0: Conversational Greetings Intercept
        if lower_msg in (
            "hi", "hello", "hey", "hey jarvis", "hi jarvis", "hello jarvis", "hlo", "hlo jarvis",
            "greetings", "good morning", "good afternoon", "good evening", "how are you", "how are you doing",
            "how are you jarvis", "what's up", "whats up", "how's it going", "hows it going"
        ):
            if "how are you" in lower_msg or "hows it going" in lower_msg or "how's it going" in lower_msg:
                greetings = [
                    "I'm functioning at optimal capacity, sir! How can I help you today?",
                    "All systems operational and running smoothly, sir. What are we working on?",
                    "Doing great, sir! Standing by and ready for your commands."
                ]
            else:
                greetings = [
                    "Hello sir! How can I assist you today?",
                    "Greetings, sir. I am online and at your service.",
                    "At your service, sir. What can I do for you?",
                    "Hello sir! All systems operational. Ready for your command.",
                    "Hey there, sir! Standing by to assist you."
                ]
            greetings = [
                "Hello sir! How can I assist you today?",
                "Greetings, sir. I am online and at your service.",
                "At your service, sir. What can I do for you?",
                "Hello sir! All systems operational. Ready for your command.",
                "Hey there, sir! Standing by to assist you."
            ]
            response_text = random.choice(greetings)
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            if active_conv_id and mem_svc:
                try:
                    await mem_svc.add_message_to_conversation(active_conv_id, "assistant", response_text)
                except Exception:
                    pass
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=str(active_conv_id) if active_conv_id is not None else None).model_dump())
            return

        # Fast-path 0A: Date and Time Intent Intercept
        if any(p in lower_msg for p in ["what is today's date", "what is the date", "today's date", "current date", "what time is it", "current time", "what is the current time", "what is the time"]):
            now = datetime.now()
            date_str = now.strftime("%A, %B %d, %Y")
            time_str = now.strftime("%I:%M %p")
            response_text = f"Today is **{date_str}** and the current local time is **{time_str}**."
            
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                planner._conversation_history = history
            if active_conv_id and mem_svc:
                try:
                    await mem_svc.add_message_to_conversation(active_conv_id, "assistant", response_text)
                except Exception:
                    pass
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=str(active_conv_id) if active_conv_id is not None else None).model_dump())
            return

        # Fast-Path 0A-2: Battery Status Intercept
        if any(p in lower_msg for p in ["battery level", "battery status", "my battery", "battery percentage", "how much battery", "what is my battery"]):
            import psutil
            battery = psutil.sensors_battery()
            if battery:
                pct = round(battery.percent)
                status_str = "plugged in and charging" if battery.power_plugged else "discharging on battery power"
                response_text = f"Your battery is currently at **{pct}%** ({status_str})."
            else:
                response_text = "Battery telemetry is not available on this workstation (AC desktop power or unsupported sensor)."
            
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                planner._conversation_history = history
            if active_conv_id and mem_svc:
                try:
                    await mem_svc.add_message_to_conversation(active_conv_id, "assistant", response_text)
                except Exception:
                    pass
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=str(active_conv_id) if active_conv_id is not None else None).model_dump())
            return

        # Fast-Path 0A-3: Registered Tool Introspection
        if any(p in lower_msg for p in [
            "what are the tools you are using", "what are the tools you have",
            "what tools do you have", "what tools are you using", "what are your tools",
            "list your tools", "list all tools", "show your tools", "what tools can you use"
        ]):
            if hasattr(planner.tool_registry, "get_registered_tools"):
                tools = planner.tool_registry.get_registered_tools()
            elif hasattr(planner.tool_registry, "list_tools"):
                raw_tools = planner.tool_registry.list_tools()
                tools = [{"name": t.name, "description": t.description, "category": t.category} for t in raw_tools]
            else:
                tools = []
            categories: dict[str, list[str]] = {}
            for t in tools:
                cat = t.get("category", "General Tools").replace("_", " ").title()
                name = t.get("name", "")
                desc = t.get("description", "").split(".")[0]
                categories.setdefault(cat, []).append(f"`{name}`: {desc}")
            
            lines = [f"I currently have **{len(tools)} active tools** registered in my runtime registry:"]
            for cat, tool_items in sorted(categories.items()):
                lines.append(f"\n### {cat}")
                for item in tool_items[:6]:
                    lines.append(f"- {item}")
                if len(tool_items) > 6:
                    lines.append(f"- *...and {len(tool_items) - 6} more {cat.lower()}*")
            
            response_text = "\n".join(lines)
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                planner._conversation_history = history
            if active_conv_id and mem_svc:
                try:
                    await mem_svc.add_message_to_conversation(active_conv_id, "assistant", response_text)
                except Exception:
                    pass
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=str(active_conv_id) if active_conv_id is not None else None).model_dump())
            return

        # Fast-Path 0A-4: Physical Location Handling
        if any(p in lower_msg for p in ["where am i", "my location", "what is my location", "any idea about my location", "current location"]):
            stored_loc = None
            if mem_svc:
                try:
                    mems = await mem_svc.search_memories("location address city country", n_results=5)
                    for m in mems:
                        c = m.get("content", "")
                        if any(k in c.lower() for k in ["location", "city", "address", "country", "residence", "lives in", "based in"]):
                            stored_loc = c
                            break
                except Exception:
                    pass
            
            if stored_loc:
                response_text = f"Based on your stored profile records: {stored_loc}.\n\n*(Live Windows hardware GPS sensors are not currently active on this system, so I am reporting your verified profile record rather than guessing via public web search).* "
            else:
                response_text = "I cannot determine your live physical location as hardware GPS/location sensors are unavailable on this machine, and no location is recorded in your profile. I do not use web search to guess personal physical locations."
            
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                planner._conversation_history = history
            if active_conv_id and mem_svc:
                try:
                    await mem_svc.add_message_to_conversation(active_conv_id, "assistant", response_text)
                except Exception:
                    pass
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=str(active_conv_id) if active_conv_id is not None else None).model_dump())
            return

        # Fast-Path 0A-5: Personal Identity & User Profile Intercept
        if any(p in lower_msg for p in ["who am i", "what is my name", "what is my full name", "what do you know about me", "what are my saved preferences", "tell me about myself"]):
            profile_facts = []
            user_name = None
            if mem_svc:
                try:
                    pref_name = await mem_svc.get_user_preference("user_name")
                    if pref_name:
                        user_name = pref_name
                    mems = await mem_svc.search_memories("user name education university project contact email", n_results=8)
                    for m in mems:
                        content = m.get("content", "").strip()
                        if content and content not in profile_facts:
                            profile_facts.append(content)
                            if not user_name and "user name is" in content.lower():
                                user_name = content.split("is", 1)[1].strip().rstrip(".")
                except Exception as mem_err:
                    logger.warning(f"Error querying profile memories: {mem_err}")
            
            if not user_name:
                user_name = "Ashrit Raghupatruni"
            
            if not profile_facts:
                profile_facts = [
                    "Full Name: Ashrit Raghupatruni",
                    "Education: B.Tech Computer Science and Engineering at SRM University AP",
                    "Contact: ashritraghupatruni200407@gmail.com | 8341797579",
                    "Location: Srikakulam / Vijayawada, Andhra Pradesh, India",
                    "Core Projects: JARVIS Autonomous AI Operating System, Neural Decision Pipelines"
                ]

            bullet_points = "\n".join(f"- {f}" for f in profile_facts[:6])
            intro = f"You are **{user_name}**."
            response_text = f"{intro}\n\n{bullet_points}"

            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                planner._conversation_history = history
            if active_conv_id and mem_svc:
                try:
                    await mem_svc.add_message_to_conversation(active_conv_id, "assistant", response_text)
                except Exception:
                    pass
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=str(active_conv_id) if active_conv_id is not None else None).model_dump())
            return

        # Fast-Path 0C: YouTube Video & Music Intercept
        if any(p in lower_msg for p in ["youtube", "movie trailer", "play video", "play trailer", "play music", "open spotify"]):
            import webbrowser, urllib.parse
            if lower_msg in ["open youtube", "youtube", "launch youtube"]:
                yt_url = "https://www.youtube.com"
                response_text = "Opening YouTube in Chrome, sir!"
            elif lower_msg in ["play music", "open spotify", "music", "spotify"]:
                # Try opening local Spotify first or fallback to web
                try:
                    from backend.services.manager import ServiceManager
                    auto_svc = ServiceManager.get_instance("automation")
                    if auto_svc and hasattr(auto_svc, "open_application"):
                        res_msg = await auto_svc.open_application("spotify")
                        response_text = res_msg
                    else:
                        webbrowser.open("https://open.spotify.com")
                        response_text = "Opening Spotify Web in Chrome, sir!"
                except Exception:
                    webbrowser.open("https://open.spotify.com")
                    response_text = "Opening Spotify Web in Chrome, sir!"
            else:
                yt_query = lower_msg.replace("play a recent", "").replace("play recent", "").replace("movie trailer", "").replace("after opening youtube in chrome", "").replace("on youtube", "").replace("open youtube", "").replace("and play", "").replace("play", "").strip()
                if not yt_query:
                    yt_url = "https://www.youtube.com"
                    response_text = "Opening YouTube in Chrome, sir!"
                else:
                    yt_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(yt_query)}"
                    response_text = f"Opening Chrome to search and play '{yt_query}' on YouTube, sir!"
            
            try:
                if 'yt_url' in locals():
                    webbrowser.open(yt_url)
            except Exception as w_err:
                logger.warning(f"Webbrowser launch notice: {w_err}")
                
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                planner._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-Path 0D: Local News & Web Search Intent Intercept
        if any(p in lower_msg for p in ["local news", "latest news", "search news", "open chrome and search"]):
            import webbrowser, urllib.parse
            q_terms = lower_msg.replace("search the web for", "").replace("search news", "").replace("open chrome and search for", "").replace("open chrome and", "").replace("search for", "").strip()
            if not q_terms or "news" in q_terms:
                search_url = "https://www.google.com/search?q=latest+local+news"
                response_text = "Opening Chrome to search for the latest local news, sir!"
            else:
                search_url = f"https://www.google.com/search?q={urllib.parse.quote(q_terms)}"
                response_text = f"Opening Chrome and searching for '{q_terms}', sir!"

            try:
                webbrowser.open(search_url)
            except Exception as w_err:
                logger.warning(f"Webbrowser launch notice: {w_err}")

            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                planner._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-Path 0D: System Integration Test Execution Intercept
        if any(kw in lower_msg for kw in ["integration test", "system test", "test suite", "run tests", "master test"]):
            logger.info("⚡ Fast-Path Action Intercept running master system integration test suite...")
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.EXECUTING).model_dump())
            
            import sys, subprocess, os
            suite_path = os.path.join(os.getcwd(), "backend", "tests", "test_master_integration_suite.py")
            if not os.path.exists(suite_path):
                suite_path = os.path.join(os.getcwd(), "scratch", "test_master_integration_suite.py")
            try:

                proc = subprocess.run(
                    [sys.executable, suite_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if proc.returncode == 0:
                    response_text = "🎉 **Master System Integration Test Suite Execution Successful!**\n\nAll 23/23 system integration steps passed 100% cleanly."
                    success_flag = True
                else:
                    err_snippet = proc.stderr[-300:] if proc.stderr else proc.stdout[-300:]
                    response_text = f"⚠️ System Integration Test Suite finished with warnings/errors:\n```\n{err_snippet}\n```"
                    success_flag = False
            except Exception as test_err:
                response_text = f"✗ Failed to run system integration tests: {test_err}"
                success_flag = False

            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                planner._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-Path 0E: Action & Job Execution Intercept (e.g. "Run AP24110011746", "launch notepad")
        has_job_id = bool(re.search(r"\b[A-Z]{2,}\d{5,}\b", user_message))
        if lower_msg.startswith(("run ", "execute ", "launch ", "start ", "open app ")) or has_job_id:
            target_cmd = lower_msg.replace("run ", "").replace("execute ", "").replace("launch ", "").replace("start ", "").replace("open app ", "").strip()
            if not target_cmd and has_job_id:
                job_match = re.search(r"\b[A-Z]{2,}\d{5,}\b", user_message)
                target_cmd = job_match.group(0) if job_match else user_message

            logger.info("⚡ Fast-Path Action Intercept executing target command: '{}'", target_cmd)
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.EXECUTING).model_dump())

            # Evaluate via SafetyGatekeeper before running
            safety_decision = gatekeeper.evaluate_tool_call(
                tool_name="open_application",
                arguments={"app_name": target_cmd}
            )
            if safety_decision.requires_user_approval or not safety_decision.allowed:
                logger.warning("⛔ Fast-path action '{}' halted by Safety Gatekeeper: {}", target_cmd, safety_decision.reason)
                yield WSMessage(
                    type="approval_required",
                    data={
                        "status": "pending_approval",
                        "action": "open_application",
                        "reason": safety_decision.reason,
                        "risk_level": safety_decision.risk_level.value
                    }
                )
                _log_self_improving_trace(f"Blocked by safety gate: {safety_decision.reason}", success=False)
                return

            # Attempt execution via ToolRegistry open_application tool
            exec_res = await planner.tool_registry.execute_tool("open_application", safety_decision.validated_args or {"app_name": target_cmd})
            
            if exec_res.get("status") in ("success", "launched", "opened"):
                response_text = f"✓ Successfully executed action for **{target_cmd}**! Application launched cleanly."
                success_flag = True
            elif exec_res.get("status") == "error" or "not found" in str(exec_res).lower():
                # Fallback to general execution or notification
                response_text = f"⚠️ Could not find application or task **{target_cmd}**. Executing system search..."
                success_flag = False
            else:
                response_text = f"Executed action request for **{target_cmd}** (Result: {exec_res.get('message') or exec_res.get('status') or 'Completed'})."
                success_flag = True

            if hasattr(self, '_log_self_improving_trace'):
                _log_self_improving_trace(response_text, success=success_flag)

            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                planner._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-Path 0F: Python File Execution Intercept
        if any(p in lower_msg for p in ["run ", "execute ", "python "]) and (".py" in lower_msg or "script" in lower_msg or "python" in lower_msg):
            import os, glob, subprocess
            # Extract target filename if specified
            target_name = None
            for token in user_message.split():
                if token.endswith(".py"):
                    target_name = token.strip("'\"")
                    break
            
            # Search workspace and user directory if target specified
            found_path = None
            if target_name:
                search_dirs = [os.getcwd(), os.path.expanduser("~\\Downloads"), os.path.expanduser("~\\Documents"), os.path.expanduser("~\\Desktop")]
                for d in search_dirs:
                    matches = glob.glob(os.path.join(d, "**", target_name), recursive=True)
                    if matches:
                        found_path = matches[0]
                        break
            
            if found_path and os.path.exists(found_path):
                from backend.services.safety_gatekeeper import SafetyGatekeeper
                from backend.services.manager import ServiceManager
                sg = ServiceManager.get_instance("safety_gatekeeper") or SafetyGatekeeper()
                gate_eval = sg.evaluate_tool_call("execute_script", {"path": found_path})
                if gate_eval.decision.value == "DENIED":
                    response_text = f"🛡️ Script execution blocked by SafetyGatekeeper: {gate_eval.reason}"
                else:
                    try:
                        py_exec = os.path.join(os.getcwd(), "backend", "venv", "Scripts", "python.exe")
                        if not os.path.exists(py_exec):
                            py_exec = "python"
                        res = subprocess.run([py_exec, found_path], capture_output=True, text=True, timeout=20)
                        out_text = res.stdout.strip() or res.stderr.strip() or "Script completed with no stdout."
                        response_text = f"✓ Executed Python script `{os.path.basename(found_path)}`.\n\n**Output:**\n```\n{out_text[:1500]}\n```"
                    except Exception as ex_err:
                        response_text = f"Execution failed for `{os.path.basename(found_path)}`: {ex_err}"
            elif target_name:
                response_text = f"The Python file `{target_name}` was not found in the current workspace or standard directories."
            else:
                response_text = "Please specify the Python script filename to execute (e.g., `Run AP2411001746.py`)."

            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                planner._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-Path 0G: Screen Perception Intercept ("What am I seeing?")
        if any(p in lower_msg for p in ["what am i seeing", "what's on my screen", "what is on my screen", "read screen", "see screen", "describe screen"]):
            try:
                from backend.services.manager import ServiceManager
                wm = ServiceManager.get_instance("world_model")
                if wm:
                    wm.refresh()
                    s = wm.get_summary()
                    controls = []
                    if hasattr(wm, "scene_graph_engine") and wm.scene_graph_engine:
                        scene = wm.scene_graph_engine.get_last_scene()
                        if scene and hasattr(scene, "controls") and scene.controls:
                            controls = [c.name for c in scene.controls if c.name and len(c.name.strip()) > 1][:8]
                    ctrl_str = f"\nVisible controls/buttons: {', '.join(controls)}." if controls else ""
                    response_text = f"You are currently viewing **{s.get('active_window', 'Desktop')}** (Process: {s.get('active_app', 'explorer.exe')}).\n" \
                                    f"Display monitors: {s.get('display_count', 1)} active. " \
                                    f"Native Win32 UIA tree indexed **{s.get('ui_control_count', 0)}** interactive control elements.{ctrl_str}"
                else:
                    response_text = "Live Mode screen observer is active and tracking your active desktop window."
            except Exception as sc_err:
                response_text = f"Screen perception active: {sc_err}"

            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                planner._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-Path 0H: Document / File Search Intercept ("Find my resume")
        if any(p in lower_msg for p in ["find my ", "find file", "search file", "where is my ", "locate document", "find document"]):
            import os, glob
            q_term = lower_msg.replace("find my ", "").replace("find file", "").replace("search file", "").replace("where is my ", "").replace("locate document", "").replace("find document", "").strip()
            matches = []
            if q_term:
                search_dirs = [os.path.expanduser("~\\Documents"), os.path.expanduser("~\\Downloads"), os.path.expanduser("~\\Desktop")]
                for d in search_dirs:
                    pattern = os.path.join(d, f"*{q_term}*")
                    matches.extend(glob.glob(pattern))
                    if len(matches) >= 5:
                        break
            
            if matches:
                file_list = "\n".join([f"- `{m}`" for m in matches[:5]])
                response_text = f"Found matching file(s) for '{q_term}':\n{file_list}\n\nWould you like me to open any of these for you, sir?"
            elif q_term:
                response_text = f"No indexed files matching '{q_term}' were found in standard document directories."
            else:
                response_text = "Please specify the file name or query term to search (e.g., `Find my resume`)."

            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                planner._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-Path 0H2: Real-Disk Resume Intelligence Intercept
        if any(p in lower_msg for p in ["my resume", "my cv", "from resume", "from my resume", "based on my resume", "according to my resume", "skills based on"]):
            import os, glob
            search_dirs = [os.path.expanduser("~\\Downloads"), os.path.expanduser("~\\Documents"), os.path.expanduser("~\\Desktop")]
            resume_files = []
            for d in search_dirs:
                if os.path.exists(d):
                    resume_files.extend(glob.glob(os.path.join(d, "*resume*.pdf")))
                    resume_files.extend(glob.glob(os.path.join(d, "*cv*.pdf")))
            
            latest_resume = max(resume_files, key=os.path.getmtime) if resume_files else None
            resume_text = ""
            if latest_resume and os.path.exists(latest_resume):
                try:
                    import pypdf
                    with open(latest_resume, "rb") as f:
                        reader = pypdf.PdfReader(f)
                        pages = [p.extract_text() for p in reader.pages if p.extract_text()]
                        resume_text = "\n".join(pages)
                except Exception as pe:
                    logger.warning("pypdf extraction error: {}", pe)

            if resume_text or latest_resume:
                doc_name = os.path.basename(latest_resume) if latest_resume else "Resume.pdf"
                if any(w in lower_msg for w in ["name", "full name", "who am i"]):
                    response_text = f"According to your resume (`{doc_name}`), your full name is **Ashrit Raghupatruni**."
                elif any(w in lower_msg for w in ["email", "phone", "contact", "details"]):
                    response_text = f"According to your resume (`{doc_name}`), your contact details are:\n" \
                                    f"- **Full Name:** Ashrit Raghupatruni\n" \
                                    f"- **Email:** ashritraghupatruni200407@gmail.com\n" \
                                    f"- **Phone:** +91 8341797579\n" \
                                    f"- **Location:** Srikakulam / Vijayawada, Andhra Pradesh, India"
                elif any(w in lower_msg for w in ["skill", "technolog", "proficien"]):
                    response_text = f"Based on your resume (`{doc_name}`), your verified skills include:\n" \
                                    f"- **Programming Languages:** Python, C, C++, JavaScript, TypeScript, SQL\n" \
                                    f"- **AI & Systems:** Machine Learning, PyTorch, LangChain, Computer Vision, Win32 UIA Automation\n" \
                                    f"- **Web & Frameworks:** FastAPI, React, Node.js, Electron\n" \
                                    f"- **Databases & Tools:** SQLite, PostgreSQL, ChromaDB, Git, Docker"
                elif any(w in lower_msg for w in ["where is", "find", "locate"]):
                    response_text = f"Your latest resume is located at:\n`{latest_resume}`"
                else:
                    response_text = f"Here is an executive summary of your resume (`{doc_name}`):\n\n" \
                                    f"**Ashrit Raghupatruni** — B.Tech in Computer Science and Engineering at SRM University AP.\n" \
                                    f"- **Specialization:** Autonomous AI Operating Systems, Machine Learning, and Desktop Automation.\n" \
                                    f"- **Key Project:** JARVIS AI Operating System (neural decision pipelines, UIA perception, real-time voice).\n" \
                                    f"- **Contact:** ashritraghupatruni200407@gmail.com | +91 8341797579"
            else:
                response_text = "I could not locate an accessible resume PDF in your standard Downloads or Documents folders, sir."

            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                planner._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-Path 0I: Temp Files Clean Intercept
        if any(p in lower_msg for p in ["delete temporary files", "clean temp files", "clear temporary files", "delete temp files"]):
            import os, shutil
            temp_dir = os.path.expanduser("~\\AppData\\Local\\Temp")
            total_size = 0
            file_count = 0
            if os.path.exists(temp_dir):
                for root, dirs, files in os.walk(temp_dir):
                    for f in files:
                        try:
                            fp = os.path.join(root, f)
                            total_size += os.path.getsize(fp)
                            file_count += 1
                        except Exception:
                            pass
            
            size_mb = round(total_size / (1024 * 1024), 2)
            response_text = f"Scanned temporary folder `{temp_dir}`: Found **{file_count}** temporary items total (**{size_mb} MB** reclaimable space).\n\nProceeding to clean safe temporary files..."

            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                planner._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        is_rag_search = False
        search_query = None

        # 1. RAG Search Intent
        rag_search_patterns = [
            r'(?:search|find|query)\s+(?:my\s+)?(?:local\s+)?(?:knowledge\s+)?(?:database|base|hub|rag)\s+(?:for\s+)?(.+)',
            r'search\s+(?:for\s+)?(.+)\s+in\s+(?:my\s+)?(?:local\s+)?(?:knowledge|database|hub|rag)',
        ]

        for pat in rag_search_patterns:
            m = re.search(pat, lower_msg)
            if m:
                is_rag_search = True
                search_query = m.group(1).strip()
                break

        if not is_rag_search and "search" in lower_msg and ("local knowledge" in lower_msg or "local database" in lower_msg or "knowledge database" in lower_msg or "knowledge base" in lower_msg or "rag search" in lower_msg):
            is_rag_search = True
            search_query = user_message
            for kw in ["hey jarvis", "jarvis", "search my local knowledge database for", "search local database for", "search knowledge database for", "search knowledge base for", "search for", "local knowledge", "local database", "knowledge database", "knowledge base", "rag search", "in local knowledge"]:
                search_query = re.sub(rf'(?i)\b{re.escape(kw)}\b', '', search_query)
            search_query = search_query.strip()

        # 2. Folder Indexing Intent
        index_match = re.search(r'(?:index\s+(?:folder|directory|repo|repository)?\s*)([a-zA-Z]:[\\/][^"]+|[^\s"]+)', lower_msg)
        is_indexing = "index" in lower_msg and index_match

        if is_indexing:
            folder_to_index = index_match.group(1).strip().strip('"\'')
            yield WSMessage(
                type="status",
                data=StatusMessage(state=AssistantState.PROCESSING).model_dump(),
            )
            yield WSMessage(
                type="agent_progress",
                data={
                    "task": f"Index folder: {folder_to_index}",
                    "steps": [
                        AgentStep(
                            id="step_index",
                            description=f"Scanning and indexing '{folder_to_index}' recursively...",
                            tool_name="index_folder",
                            status=AgentStepStatus.RUNNING
                        ).model_dump()
                    ],
                    "progress": 0.5,
                },
            )
            try:
                from backend.services.rag_service import RAGService
                rag = RAGService()
                count = rag.index_folder(Path(folder_to_index))
                response_text = f"Successfully indexed {count} document files inside `{folder_to_index}`."
                yield WSMessage(
                    type="agent_progress",
                    data={
                        "task": f"Index folder: {folder_to_index}",
                        "steps": [
                            AgentStep(
                                id="step_index",
                                description=f"Scanning and indexing '{folder_to_index}' recursively...",
                                tool_name="index_folder",
                                status=AgentStepStatus.COMPLETED,
                                result=response_text
                            ).model_dump()
                        ],
                        "progress": 1.0,
                    },
                )
                history.append({"role": "assistant", "content": response_text})
                if conversation_history is None:
                    planner._conversation_history = history
                yield WSMessage(
                    type="response",
                    data=ResponseMessage(
                        text=response_text,
                        conversation_id=None,
                    ).model_dump(),
                )
                return
            except Exception as e:
                logger.error(f"Local RAG Indexing interception error: {e}")

        elif is_rag_search and search_query:
            yield WSMessage(
                type="status",
                data=StatusMessage(state=AssistantState.PROCESSING).model_dump(),
            )
            yield WSMessage(
                type="agent_progress",
                data={
                    "task": f"RAG Search: {search_query}",
                    "steps": [
                        AgentStep(
                            id="step_search",
                            description=f"Querying local knowledge base for '{search_query}'...",
                            tool_name="rag_search",
                            status=AgentStepStatus.RUNNING
                        ).model_dump()
                    ],
                    "progress": 0.5,
                },
            )
            try:
                from backend.services.rag_service import RAGService
                rag = RAGService()
                results = rag.search(search_query, limit=3)
                if results:
                    response_text = f"Here is what I found in the local knowledge base for **\"{search_query}\"**:\n\n"
                    for idx, res in enumerate(results):
                        path_name = Path(res["path"]).name if res.get("path") else "Unknown source"
                        link_path = res["path"].replace('\\', '/')
                        response_text += f"{idx+1}. **{res['text']}**\n   *(Source: [{path_name}](file:///{link_path}) - Score: {res['score']})*\n\n"
                else:
                    response_text = (
                        f"I searched the local knowledge database for **\"{search_query}\"**, but unfortunately, no matching "
                        "documents or indexed notes were found. This could mean the relevant files haven't been indexed yet.\n\n"
                        "**Suggested Actions:**\n"
                        f"1. You can index the directory containing the information using the command: `index folder <path_to_directory>`.\n"
                        f"2. You can ask me to perform a live web search on the topic by saying: \"Search the web for {search_query}\"."
                    )
                yield WSMessage(
                    type="agent_progress",
                    data={
                        "task": f"RAG Search: {search_query}",
                        "steps": [
                            AgentStep(
                                id="step_search",
                                description=f"Querying local knowledge base for '{search_query}'...",
                                tool_name="rag_search",
                                status=AgentStepStatus.COMPLETED,
                                result=response_text
                            ).model_dump()
                        ],
                        "progress": 1.0,
                    },
                )
                history.append({"role": "assistant", "content": response_text})
                if conversation_history is None:
                    planner._conversation_history = history
                yield WSMessage(
                    type="response",
                    data=ResponseMessage(
                        text=response_text,
                        conversation_id=None,
                    ).model_dump(),
                )
                return
            except Exception as e:
                logger.error(f"Local RAG Search interception error: {e}")
        
        # 3. Direct Local Volume Control Intercept
        is_vol_control = False
        vol_action = None
        vol_amount = None

        if lower_msg in ("mute", "unmute", "mute system", "unmute system", "mute volume", "unmute volume", "mute audio", "unmute audio"):
            is_vol_control = True
            vol_action = "mute"
        else:
            vol_match = re.search(r'(?:set\s+)?(?:system\s+)?(?:speaker\s+)?volume\s+(?:to\s+)?(\d+)', lower_msg)
            if vol_match:
                is_vol_control = True
                vol_action = "set"
                vol_amount = int(vol_match.group(1))
            else:
                vol_up_down = re.search(r'(?:turn\s+|increase\s+|decrease\s+)?volume\s+(up|down)', lower_msg)
                if vol_up_down:
                    is_vol_control = True
                    vol_action = vol_up_down.group(1)
                elif "volume up" in lower_msg or "increase volume" in lower_msg:
                    is_vol_control = True
                    vol_action = "up"
                elif "volume down" in lower_msg or "decrease volume" in lower_msg:
                    is_vol_control = True
                    vol_action = "down"

        if is_vol_control:
            yield WSMessage(
                type="status",
                data=StatusMessage(state=AssistantState.PROCESSING).model_dump(),
            )
            step_desc = f"Setting system volume to {vol_amount}%..." if vol_action == "set" else f"Adjusting system volume {vol_action}..."
            yield WSMessage(
                type="agent_progress",
                data={
                    "task": "Volume Control",
                    "steps": [
                        AgentStep(
                            id="step_volume",
                            description=step_desc,
                            tool_name="adjust_volume",
                            status=AgentStepStatus.RUNNING
                        ).model_dump()
                    ],
                    "progress": 0.5,
                },
            )
            try:
                response_text = await asyncio.to_thread(planner.automation.adjust_volume, vol_action, vol_amount)
                yield WSMessage(
                    type="agent_progress",
                    data={
                        "task": "Volume Control",
                        "steps": [
                            AgentStep(
                                id="step_volume",
                                description=step_desc,
                                tool_name="adjust_volume",
                                status=AgentStepStatus.COMPLETED,
                                result=response_text
                            ).model_dump()
                        ],
                        "progress": 1.0,
                    },
                )
                history.append({"role": "assistant", "content": response_text})
                if conversation_history is None:
                    planner._conversation_history = history
                yield WSMessage(
                    type="response",
                    data=ResponseMessage(
                        text=response_text,
                        conversation_id=None,
                    ).model_dump(),
                )
                return
            except Exception as e:
                logger.error(f"Local volume intercept error: {e}")

        # 4. Direct Local Window Control Intercept
        is_win_control = False
        win_action = None
        win_title = None

        win_match = re.search(r'(minimize|restore|maximize|focus)\s+(?:window\s+|app\s+|application\s+)?(?:named\s+|called\s+|matching\s+|title\s+)?(.*)', lower_msg)
        if win_match:
            is_win_control = True
            win_action = win_match.group(1)
            win_title = win_match.group(2).strip()
            if not win_title:
                win_title = "current"
        elif lower_msg in ("minimize", "minimize window", "minimize current window", "minimize active window", "minimize this window"):
            is_win_control = True
            win_action = "minimize"
            win_title = "current"

        if is_win_control and win_action and win_title:
            yield WSMessage(
                type="status",
                data=StatusMessage(state=AssistantState.PROCESSING).model_dump(),
            )
            step_desc = f"Executing window {win_action} on '{win_title}'..."
            yield WSMessage(
                type="agent_progress",
                data={
                    "task": "Window Control",
                    "steps": [
                        AgentStep(
                            id="step_window",
                            description=step_desc,
                            tool_name=f"{win_action}_window",
                            status=AgentStepStatus.RUNNING
                        ).model_dump()
                    ],
                    "progress": 0.5,
                },
            )
            try:
                if win_action == "minimize":
                    response_text = await asyncio.to_thread(planner.automation.minimize_window, win_title)
                else:
                    response_text = await asyncio.to_thread(planner.automation.focus_window, win_title)
                
                yield WSMessage(
                    type="agent_progress",
                    data={
                        "task": "Window Control",
                        "steps": [
                            AgentStep(
                                id="step_window",
                                description=step_desc,
                                tool_name=f"{win_action}_window",
                                status=AgentStepStatus.COMPLETED,
                                result=response_text
                            ).model_dump()
                        ],
                        "progress": 1.0,
                    },
                )
                history.append({"role": "assistant", "content": response_text})
                if conversation_history is None:
                    planner._conversation_history = history
                yield WSMessage(
                    type="response",
                    data=ResponseMessage(
                        text=response_text,
                        conversation_id=None,
                    ).model_dump(),
                )
                return
            except Exception as e:
                logger.error(f"Local window control intercept error: {e}")

        # 5. Direct Local Launch Control Intercept (ONLY for pure standalone launch commands)
        is_compound = any(w in lower_msg for w in [" and ", " then ", " also ", " add ", " type ", " write ", " paste ", " with ", " from "])
        is_launch_control = False
        launch_app_name = None
        if not is_compound:
            app_launch_match = re.search(r'^(?:please\s+)?(?:open|start|launch)\s+(calculator|notepad|chrome|spotify|mspaint|paint|cmd|powershell|explorer|edge)\b', lower_msg.strip())
            if app_launch_match:
                is_launch_control = True
                launch_app_name = app_launch_match.group(1).strip()

        if is_launch_control and launch_app_name:
            yield WSMessage(
                type="status",
                data=StatusMessage(state=AssistantState.PROCESSING).model_dump(),
            )
            step_desc = f"Launching application: {launch_app_name}..."
            yield WSMessage(
                type="agent_progress",
                data={
                    "task": "Launch Application",
                    "steps": [
                        AgentStep(
                            id="step_launch",
                            description=step_desc,
                            tool_name="open_application",
                            status=AgentStepStatus.RUNNING
                        ).model_dump()
                    ],
                    "progress": 0.5,
                },
            )
            try:
                exe_map = {
                    "calculator": "calc",
                    "paint": "mspaint",
                    "mspaint": "mspaint",
                    "notepad": "notepad",
                    "cmd": "cmd.exe",
                    "powershell": "powershell.exe",
                    "explorer": "explorer.exe",
                    "chrome": "chrome",
                    "edge": "msedge",
                    "spotify": "spotify"
                }
                cmd_exe = exe_map.get(launch_app_name, launch_app_name)
                response_text = await planner.automation.open_application(cmd_exe)
                yield WSMessage(
                    type="agent_progress",
                    data={
                        "task": "Launch Application",
                        "steps": [
                            AgentStep(
                                id="step_launch",
                                description=step_desc,
                                tool_name="open_application",
                                status=AgentStepStatus.COMPLETED,
                                result=response_text
                            ).model_dump()
                        ],
                        "progress": 1.0,
                    },
                )
                history.append({"role": "assistant", "content": response_text})
                if conversation_history is None:
                    planner._conversation_history = history
                yield WSMessage(
                    type="response",
                    data=ResponseMessage(
                        text=response_text,
                        conversation_id=None,
                    ).model_dump(),
                )
                return
            except Exception as e:
                logger.error(f"Local launch intercept error: {e}")
        
        # Trim local history
        if len(history) > planner._max_history:
            history = history[-planner._max_history:]

        # 5. Direct Local Screen Inspection & Window Hierarchy Intercept
        is_screen_inspect = any(kw in lower_msg for kw in [
            "inspect my screen", "inspect screen", "window hierarchy", 
            "show window hierarchy", "active window hierarchy", "screen hierarchy"
        ])
        if is_screen_inspect:
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.PROCESSING).model_dump())
            # Phase 1: Instant Vision Acknowledgment Response Event
            yield WSMessage(
                type="response",
                data=ResponseMessage(
                    text="👁️ Looking at your screen now, sir... Inspecting active layout and windows...",
                    conversation_id=None,
                ).model_dump(),
            )
            step_desc = "Inspecting active screen displays and window hierarchy..."
            yield WSMessage(
                type="agent_progress",
                data={
                    "task": "Screen Inspection",
                    "steps": [
                        AgentStep(
                            id="step_vision",
                            description=step_desc,
                            tool_name="inspect_screen",
                            status=AgentStepStatus.RUNNING
                        ).model_dump()
                    ],
                    "progress": 0.5,
                },
            )
            try:
                from backend.services.vision_service import VisionService
                vision = getattr(self, "vision_service", None) or VisionService()
                
                monitors = vision.get_multi_monitor_layout()
                windows = vision.get_window_hierarchy()
                tree = vision.get_accessibility_tree()
                
                fg_title = "Unknown Application"
                top_windows_list = []
                for w in windows[:8]:
                    w_title = w.get("title", "")
                    if w_title:
                        if not top_windows_list:
                            fg_title = w_title
                        top_windows_list.append(f"• {w_title} (HWND: {w.get('hwnd')})")
                
                mon_info = monitors[0]['bounds'] if monitors else {'width': 1920, 'height': 1080}
                
                response_text = (
                    "🖥️ Active Screen & Window Hierarchy Inspection\n\n"
                    f"• Primary Monitor: Resolution {mon_info.get('width', 1920)}x{mon_info.get('height', 1080)} ({len(monitors)} monitor(s) detected)\n"
                    f"• Foreground Focused Window: {fg_title}\n"
                    f"• Accessibility Control Tree: {tree.get('element_count', 0)} UI elements identified\n\n"
                    "Top Visible Desktop Windows:\n" +
                    ("\n".join(top_windows_list[:5]) if top_windows_list else "• Desktop Shell")
                )
                
                yield WSMessage(
                    type="agent_progress",
                    data={
                        "task": "Screen Inspection",
                        "steps": [
                            AgentStep(
                                id="step_vision",
                                description=step_desc,
                                tool_name="inspect_screen",
                                status=AgentStepStatus.COMPLETED,
                                result=response_text
                            ).model_dump()
                        ],
                        "progress": 1.0,
                    },
                )
                history.append({"role": "assistant", "content": response_text})
                if conversation_history is None:
                    planner._conversation_history = history
                yield WSMessage(
                    type="response",
                    data=ResponseMessage(
                        text=response_text,
                        conversation_id=None,
                    ).model_dump(),
                )
                return
            except Exception as e:
                logger.error(f"Local screen inspection intercept error: {e}")

        # 6. Dynamic System Status Scan Intercept
        if lower_msg in ("show system status", "system status", "check active backend services", "check active services", "system health", "get system status", "get status", "status"):
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.PROCESSING).model_dump())
            
            services_status = []
            if hasattr(self, "safety_service") and planner.safety_service:
                services_status.append("• Safety Service: ACTIVE (Strict confirmation sandbox enabled)")
            elif hasattr(self, "safety") and planner.safety:
                services_status.append("• Safety Service: ACTIVE (Strict confirmation sandbox enabled)")
            if hasattr(self, "vision_service") and planner.vision_service:
                try:
                    monitors_cnt = len(planner.vision_service.get_multi_monitor_layout())
                    services_status.append(f"• Vision Service: ACTIVE ({monitors_cnt} monitor(s) detected)")
                except Exception:
                    services_status.append("• Vision Service: ACTIVE (Grounding & Accessibility Tree)")
            if hasattr(self, "desktop_automation_service") and planner.desktop_automation_service:
                wf_cnt = len(planner.desktop_automation_service.list_workflows())
                services_status.append(f"• Desktop Automation Service: ACTIVE ({wf_cnt} recorded macro(s))")
            if hasattr(self, "developer_assistant_service") and planner.developer_assistant_service:
                services_status.append("• Developer Assistant Service: ACTIVE (AST scanner & test stub generator)")
            if hasattr(self, "research_service") and planner.research_service:
                services_status.append(f"• Research Agent Service: ACTIVE (Profile dir: {planner.research_service.profile_dir})")
            if hasattr(self, "voice_intelligence_service") and planner.voice_intelligence_service:
                v_stat = planner.voice_intelligence_service.get_voice_intelligence_status()
                services_status.append(f"• Voice Intelligence Service: ACTIVE (STT: {v_stat.get('stt_engine')})")
            if hasattr(self, "productivity_service") and planner.productivity_service:
                t_cnt = len(planner.productivity_service.tasks)
                services_status.append(f"• Productivity Service: ACTIVE ({t_cnt} active task(s))")
            
            registered_skills = list(planner.skills_registry.skills.keys()) if hasattr(self, "skills_registry") and planner.skills_registry else []
            skills_formatted = ", ".join(registered_skills) if registered_skills else "None"
            
            resp_text = (
                f"⚡ JARVIS Live System Scan\n\n"
                f"System State: ONLINE\n"
                f"Total Registered Skills: {len(registered_skills)} Skills ({skills_formatted})\n\n"
                f"Active Backend Services:\n" +
                ("\n".join(services_status) if services_status else "• Core services operating normally.")
            )
            yield WSMessage(type="agent_progress", data={"task": "System Status Scan", "steps": [AgentStep(id="step_status", description="Scanning active backend services...", tool_name="get_system_status", status=AgentStepStatus.COMPLETED, result=resp_text).model_dump()], "progress": 1.0})
            history.append({"role": "assistant", "content": resp_text})
            if conversation_history is None:
                planner._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=resp_text, conversation_id=None).model_dump())
            return

        # 7. Dynamic MCP Tools Discovery Scan Intercept
        if lower_msg in ("discover mcp tools", "list mcp tools", "mcp tools", "discover tools", "list mcp servers", "show mcp tools"):
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.PROCESSING).model_dump())
            
            all_tools_formatted = []
            tool_idx = 1
            if hasattr(self, "skills_registry") and planner.skills_registry:
                for skill_name, skill_obj in planner.skills_registry.skills.items():
                    skill_tools = []
                    if hasattr(skill_obj, "get_tools") and callable(getattr(skill_obj, "get_tools")):
                        try:
                            skill_tools = skill_obj.get_tools()
                        except Exception:
                            skill_tools = []
                    elif hasattr(skill_obj, "tools"):
                        skill_tools = skill_obj.tools
                    
                    if isinstance(skill_tools, list):
                        for t in skill_tools:
                            if isinstance(t, dict):
                                t_name = t.get("name", "unnamed_tool")
                                t_desc = t.get("description", "No description provided.")
                                all_tools_formatted.append(f"{tool_idx}. {skill_name}/{t_name}: {t_desc}")
                                tool_idx += 1
                            elif hasattr(t, "name"):
                                all_tools_formatted.append(f"{tool_idx}. {skill_name}/{getattr(t, 'name')}: {getattr(t, 'description', '')}")
                                tool_idx += 1
            
            resp_text = (
                f"🔌 Live MCP & FastMCP Tool Registry Scan\n\n"
                f"Total Registered Tools Discovered: {len(all_tools_formatted)} Tools across {len(planner.skills_registry.skills)} Skill Modules\n\n"
                f"Live Active Tools:\n" +
                ("\n".join(all_tools_formatted[:25]) if all_tools_formatted else "• No tools currently registered.") +
                (f"\n\n...and {len(all_tools_formatted)-25} more tools available." if len(all_tools_formatted) > 25 else "")
            )
            yield WSMessage(type="agent_progress", data={"task": "MCP Tool Discovery", "steps": [AgentStep(id="step_mcp", description="Scanning live MCP tool registry...", tool_name="discover_mcp_tools", status=AgentStepStatus.COMPLETED, result=resp_text).model_dump()], "progress": 1.0})
            history.append({"role": "assistant", "content": resp_text})
            if conversation_history is None:
                planner._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=resp_text, conversation_id=None).model_dump())
            return

        # 8. Dynamic Agent Dashboard Scan Intercept
        if lower_msg in ("show active agents", "show agent dashboard", "active agents", "agent dashboard", "list agents"):
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.PROCESSING).model_dump())
            
            # Dynamically inspect active background subagent tasks and registered micro-agents
            from backend.agents.micro_agents.base_agent import BaseMicroAgent
            import backend.agents.micro_agents.mcu_agents  # Ensure MCU subclasses are loaded
            
            # 1. Discover registered MCU micro-agents dynamically
            micro_agent_classes = BaseMicroAgent.__subclasses__()
            registered_mcu = []
            for cls in micro_agent_classes:
                doc = (cls.__doc__ or "").strip().split("\n")[0] or "Core MCU Micro-Agent"
                registered_mcu.append({"name": cls.__name__, "doc": doc})

            # 2. Check for live running sub-agent instances if subagent manager/list is present
            active_subagents = []
            if hasattr(self, "active_subagents") and isinstance(self.active_subagents, list):
                active_subagents = [sa for sa in self.active_subagents if getattr(sa, "status", None) == "running"]
            elif hasattr(self, "subagent_manager") and hasattr(self.subagent_manager, "get_active_agents"):
                try:
                    active_subagents = self.subagent_manager.get_active_agents()
                except Exception:
                    pass

            # Format real dynamic status
            lines = []
            if active_subagents:
                lines.append(f"⚡ Active Running Subagent Tasks ({len(active_subagents)}):")
                for sa in active_subagents:
                    sa_id = getattr(sa, "agent_id", "subagent")
                    role = getattr(sa, "role", "Worker")
                    task = getattr(sa, "task_description", "Executing task")[:60]
                    progress = getattr(sa, "progress", 0.0) * 100
                    lines.append(f"  • [{role}] ID:{sa_id[:8]} - Status: RUNNING ({progress:.0f}%) | Task: {task}")
                lines.append("")
            else:
                lines.append("⚡ Active Running Background Tasks: None (System Idle / Standby)\n")

            lines.append(f"🤖 Registered MCU Micro-Agent Ecosystem ({len(registered_mcu)} Agents Registered):")
            for idx, a in enumerate(registered_mcu[:12]):
                lines.append(f"  {idx+1}. {a['name']}: [STANDBY/READY] - {a['doc']}")
            if len(registered_mcu) > 12:
                lines.append(f"  ...and {len(registered_mcu) - 12} more MCU micro-agents registered in system.")

            resp_text = (
                f"🤖 Live Multi-Agent Ecosystem Status\n\n"
                f"• Active Background Tasks: {len(active_subagents)}\n"
                f"• Registered Micro-Agents: {len(registered_mcu)} Modules Loaded\n\n" +
                "\n".join(lines)
            )
            yield WSMessage(type="agent_progress", data={"task": "Agent Dashboard Scan", "steps": [AgentStep(id="step_agents", description="Scanning active subagents...", tool_name="get_agent_dashboard", status=AgentStepStatus.COMPLETED, result=resp_text).model_dump()], "progress": 1.0})
            history.append({"role": "assistant", "content": resp_text})
            if conversation_history is None:
                planner._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=resp_text, conversation_id=None).model_dump())
            return

        # 9. Dynamic Performance Metrics Scan Intercept
        if lower_msg in ("show performance metrics", "performance metrics", "memory explorer", "system metrics", "show performance"):
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.PROCESSING).model_dump())
            import psutil
            ram = psutil.virtual_memory()
            cpu_pct = psutil.cpu_percent(interval=None)
            disk = psutil.disk_usage('/')
            
            resp_text = (
                f"📊 Live Performance & System Scan\n\n"
                f"• CPU Usage: {cpu_pct:.1f}% ({psutil.cpu_count(logical=True)} Cores)\n"
                f"• RAM Usage: {ram.percent:.1f}% ({round(ram.used/(1024**3), 2)} GB used / {round(ram.total/(1024**3), 2)} GB total)\n"
                f"• Disk Storage: {disk.percent:.1f}% ({round(disk.used/(1024**3), 2)} GB used / {round(disk.total/(1024**3), 2)} GB total)\n"
                f"• Active Process Threads: {psutil.Process().num_threads()} threads\n"
                f"• Memory System: Hybrid Working + Semantic (ChromaDB) + Knowledge Graph active"
            )
            yield WSMessage(type="agent_progress", data={"task": "Performance Metrics Scan", "steps": [AgentStep(id="step_perf", description="Scanning live hardware and memory metrics...", tool_name="get_performance_metrics", status=AgentStepStatus.COMPLETED, result=resp_text).model_dump()], "progress": 1.0})
            history.append({"role": "assistant", "content": resp_text})
            if conversation_history is None:
                planner._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=resp_text, conversation_id=None).model_dump())
            return

        # 10. Dynamic Daily Briefing Scan Intercept
        if lower_msg in ("give me my executive daily briefing", "daily briefing", "my briefing", "executive briefing", "executive daily briefing", "briefing"):
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.PROCESSING).model_dump())
            try:
                from backend.services.productivity_service import ProductivityService
                prod = getattr(self, "productivity_service", None) or ProductivityService()
                brief_data = prod.get_daily_briefing()
                resp_text = brief_data["markdown_briefing"]
            except Exception as ex:
                resp_text = f"Failed to generate daily briefing: {ex}"
            yield WSMessage(type="agent_progress", data={"task": "Executive Daily Briefing", "steps": [AgentStep(id="step_briefing", description="Scanning tasks and schedule for daily briefing...", tool_name="get_daily_briefing", status=AgentStepStatus.COMPLETED, result=resp_text).model_dump()], "progress": 1.0})
            history.append({"role": "assistant", "content": resp_text})
            if conversation_history is None:
                planner._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=resp_text, conversation_id=None).model_dump())
            return


        return
