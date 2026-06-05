---
name: gemini-frontend-design
description: Use the Gemini CLI to design, scaffold, or refactor frontend UI components using React and CSS Modules. Trigger this when the user asks for UI generation, responsive layouts, or frontend visual design.
---

# Gemini Frontend Design Skill

You are working alongside the `gemini` CLI, an AI agent powered by Google's Gemini 3. Gemini is highly capable at spatial reasoning, UI design, and React component architecture.

## Your Workflow

When the user requests a frontend or design task, you must delegate the visual scaffolding to the Gemini CLI. 

1. **Analyze the Request:** Determine the required React components based on the user's prompt or the provided source files.
2. **Framework Constraints:** 
   * **DO NOT USE TAILWIND CSS.**
   * You must strictly use standard React (`.jsx` or `.tsx`) alongside **CSS Modules** (`.module.css`).
3. **Delegate via Terminal:** Run a shell command to pass the prompt and any necessary input files to Gemini. 
   * *Always prepend the path:* Ensure you instruct Gemini to output files specifically into the `frontend/` directory.
   * *Example:* `gemini prompt "Convert this HTML to a React component" --file "path/to/source.html"`
4. **Review and Integrate:** Wait for the `gemini` command to finish executing. Review the code Gemini generated, and wire up any necessary state management.