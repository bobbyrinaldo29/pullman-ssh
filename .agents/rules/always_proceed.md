---
trigger: always_on
description: Workspace execution policies and unified UI design system guidelines
---

# Workspace Development & Execution Policy

## 1. Autonomous Execution
- For the `pullman-ssh` workspace, proactively execute terminal commands, builds, typechecks, and file modifications without pausing for interactive confirmation.
- Complete end-to-end task implementation and verification automatically before concluding turns.
- Adhere strictly to file length constraints: keep all Vue components under **500 lines** and all TypeScript files under **1000 lines**. Proactively refactor and split large files into composables or subcomponents.

## 2. Iconography & Component Reusability
- Exclusively use icons from **Lucide** (`lucide-vue-next`).
- Build and structure components modularly for maximum reusability across views and dialogs.

## 3. Unified Button & UI Control Design System
All buttons, modal footers, and interactive controls across the application must strictly adhere to the following uniform styling standards:

### Border Radius
- Always standardize on **`rounded-lg`** (8px) for buttons, dialog action controls, and input elements.
- Do not mix mismatched corner radii (avoid using basic `rounded` 4px for dialog and form action buttons).

### Button Variants & Color Hierarchy
1. **Primary Action Button** (Submit, Save, Connect, Create, Apply):
   - Classes: `px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1.5`
   - Use for the singular primary confirmation or submission action in modals and forms.

2. **Secondary / Cancel Button** (Cancel, Dismiss, Back, Secondary Action):
   - Classes: `px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1.5`
   - Use for dismissal, cancellation, or neutral secondary options.

3. **Danger / Destructive Button** (Delete, Remove, Discard):
   - Solid Action: `px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-medium text-xs shadow-md transition-colors flex items-center space-x-1.5`
   - Soft / Toolbar: `px-3 py-1.5 rounded-lg bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 text-xs font-medium transition-colors flex items-center space-x-1.5`

4. **Ghost / Icon Button** (Modal close `X`, reload, header actions):
   - Classes: `p-1.5 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors`

### Interaction & Feedback
- Always include `transition-colors` on interactive buttons for smooth hover states.
- For async operations (testing, saving, connecting), show a spinning Lucide icon (`w-3.5 h-3.5 animate-spin`) and apply `disabled:opacity-50 disabled:cursor-not-allowed`.
