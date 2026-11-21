import { useContext } from "react";
// components
import { EditorMentionsContext } from "@/components/editor/embeds/mentions/context";
import type { TEditorMentionsContext } from "@/components/editor/embeds/mentions/context";

export const useEditorMentions = (): TEditorMentionsContext => {
  const context = useContext(EditorMentionsContext);
  if (context === undefined) throw new Error("useEditorMentions must be used within EditorMentionsProvider");
  return context;
};
