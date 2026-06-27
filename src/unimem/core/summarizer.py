"""Summarizer module containing BaseSummarizer, LocalSummarizer, and agent summary generators for Unimem v2.0.0."""

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List
from unimem.memory.schemas import ProjectState, Event, FileOperation
from unimem.utils.logger import logger

class BaseSummarizer(ABC):
    """Abstract class for converting event stream logs into high-level project status."""

    @abstractmethod
    def summarize(self, current_state: ProjectState, events: List[Event]) -> ProjectState:
        """Process events and update the project state summary."""
        pass


class LocalSummarizer(BaseSummarizer):
    """Local, rule-based summarizer analyzing event structures and logs to compile ProjectState."""

    def summarize(self, current_state: ProjectState, events: List[Event]) -> ProjectState:
        """Run heuristic parsing on events list to update the ProjectState."""
        logger.debug(f"Running local summarizer on {len(events)} events.")
        
        # Clone lists to avoid direct mutation issues
        completed = list(current_state.completed_features)
        in_progress = list(current_state.in_progress_features)
        important_files = set(current_state.important_files)
        decisions = list(current_state.recent_decisions)
        blocked_by = list(current_state.blocked_by)
        tools = set(current_state.tool_history)
        
        # Heuristics patterns
        feat_pattern = re.compile(r"(?:complete|finish|implement|add|create|setup)\s+([\w\s\-]{3,40})", re.IGNORECASE)
        ip_pattern = re.compile(r"(?:work\s+on|building|implementing|developing|fixing)\s+([\w\s\-]{3,40})", re.IGNORECASE)
        decision_pattern = re.compile(r"(?:decided\s+to|decision:)\s+([\w\s\-]{3,60})", re.IGNORECASE)
        blocker_pattern = re.compile(r"(?:blocked\s+by|waiting\s+for|error:)\s+([\w\s\-]{3,60})", re.IGNORECASE)
        
        for event in events:
            # 1. Update Tool History
            if event.tool and event.tool != "watcher":
                tools.add(event.tool)
                
            # 2. Update Important Files
            for f in event.files_changed:
                if f and not f.startswith(".") and not f.startswith("tests"):
                    important_files.add(f)
                    
            # 3. Analyze Event Type and Summaries
            text_to_scan = f"{event.prompt} {event.response_summary}"
            
            # Git commit messages often tell us about completed features
            if event.event_type == "git_commit" or event.git_commit:
                text_to_scan += f" {event.response_summary}"
                
            # Parse completed features
            for match in feat_pattern.finditer(text_to_scan):
                feature = match.group(1).strip()
                if feature and feature not in completed:
                    feature = feature.capitalize()
                    completed.append(feature)
                    if feature in in_progress:
                        in_progress.remove(feature)
                        
            # Parse in progress features
            for match in ip_pattern.finditer(text_to_scan):
                feature = match.group(1).strip().capitalize()
                if feature and feature not in completed and feature not in in_progress:
                    in_progress.append(feature)
                    
            # Parse decisions
            for match in decision_pattern.finditer(text_to_scan):
                dec = f"{match.group(1).strip().capitalize()} ({event.timestamp[:10]})"
                if dec not in decisions:
                    decisions.append(dec)
                    
            # Parse blockers
            for match in blocker_pattern.finditer(text_to_scan):
                blocker = match.group(1).strip().capitalize()
                if blocker and blocker not in blocked_by:
                    blocked_by.append(blocker)

        # Update lists back into state
        current_state.completed_features = completed
        current_state.in_progress_features = in_progress
        current_state.important_files = sorted(list(important_files))[:20] # Cap at 20 important files
        current_state.recent_decisions = decisions[-10:] # Keep latest 10
        current_state.blocked_by = blocked_by[-5:] # Keep latest 5
        current_state.tool_history = sorted(list(tools))
        
        # Task promotion logic
        if current_state.current_task:
            task_lower = current_state.current_task.lower()
            promoted = any(task_lower in feat.lower() for feat in completed)
            if not promoted and in_progress and any(
                task_lower in feat.lower() for feat in in_progress
            ) and bool(important_files):
                promoted = True
            if promoted:
                current_state.current_task = current_state.next_task
                current_state.next_task = ""

        # Update file history from events using delta tracking
        file_history_map = {}
        for event in events:
            task_str = getattr(event, "task", "")
            
            def add_or_update_op(path: str, op_type: str):
                file_history_map[path] = FileOperation(
                    file_path=path,
                    operation_type=op_type,
                    timestamp=event.timestamp,
                    task=task_str
                )

            if event.event_type == "file_created":
                for f in event.files_changed:
                    add_or_update_op(f, "created")
            elif event.event_type == "file_modified":
                for f in event.files_changed:
                    add_or_update_op(f, "modified")
            elif event.event_type == "file_deleted":
                for f in event.files_changed:
                    add_or_update_op(f, "deleted")
            elif event.event_type == "file_moved":
                if len(event.files_changed) >= 2:
                    add_or_update_op(event.files_changed[0], "deleted")
                    add_or_update_op(event.files_changed[1], "created")
                elif len(event.files_changed) == 1:
                    add_or_update_op(event.files_changed[0], "modified")
            elif event.files_changed and event.event_type not in ["session_start", "session_end"]:
                for f in event.files_changed:
                    add_or_update_op(f, "modified")

        current_state.file_history = list(file_history_map.values())
        return current_state


def generate_agent_summary(state: ProjectState, project_root: Path) -> str:
    """Generate a clean, structured project summary designed for AI agents."""
    # Deduce recently changed files
    recent_changes = []
    if state.file_history:
        sorted_ops = sorted(state.file_history, key=lambda x: x.timestamp, reverse=True)[:5]
        for op in sorted_ops:
            recent_changes.append(f"- `{op.file_path}` ({op.operation_type})")
    if not recent_changes:
        recent_changes.append("- No recent file changes logged.")

    # Deduce important files
    important_files = [f"- `{f}`" for f in state.important_files[:5]]
    if not important_files:
        important_files.append("- No important files identified yet.")

    # Current architecture
    arch_notes = [f"- {a}" for a in state.architecture[:5]]
    if not arch_notes:
        arch_notes.append("- No architecture notes recorded.")

    # Pending Tasks
    pending = []
    if state.current_task:
        pending.append(f"- **Current Task**: {state.current_task}")
    if state.next_task:
        pending.append(f"- **Next Task**: {state.next_task}")
    if not pending:
        pending.append("- No pending tasks assigned.")

    # Deduce Risks
    risks = []
    if state.blocked_by:
        for blocker in state.blocked_by:
            risks.append(f"- Blocked by: {blocker}")
    # Check if git is present
    if not (project_root / ".git").exists():
        risks.append("- Git repository missing (running in untracked mode).")
    if not risks:
        risks.append("- No immediate risks identified.")

    # Deduce Recommendations
    recommendations = []
    if not state.current_goal:
        recommendations.append("- Define a project goal to orient focus.")
    if not state.current_task:
        recommendations.append("- Define a current task to begin tracking progress.")
    if not state.tech_stack:
        recommendations.append("- Define your technology stack in the project settings/memory.")
    if not recommendations:
        recommendations.append("- Continue with the current task sequence.")

    tech_stack_str = ", ".join(state.tech_stack) if state.tech_stack else "Not specified"

    return f"""### 📝 Unimem Project Summary: {state.project_name}
**Description**: {state.description or "No description provided."}
**Tech Stack**: {tech_stack_str}

---

#### 🕒 Recent Changes
{chr(10).join(recent_changes)}

#### 📁 Key Files
{chr(10).join(important_files)}

#### 🏛️ Current Architecture
{chr(10).join(arch_notes)}

#### 🎯 Pending Tasks
{chr(10).join(pending)}

#### ⚠️ Risks
{chr(10).join(risks)}

#### 💡 Recommendations
{chr(10).join(recommendations)}
"""
