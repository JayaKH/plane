import { createContext } from "react";

export type TEditorMentionsContext = {
  projectId: string | undefined;
};

export const EditorMentionsContext = createContext<TEditorMentionsContext | undefined>(undefined);
