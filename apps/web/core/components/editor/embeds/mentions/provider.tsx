import { observer } from "mobx-react";

// components
import { EditorMentionsContext } from "@/components/editor/embeds/mentions/context";

export type TEditorMentionsProviderProps = {
    projectId?: string;
    children: React.ReactNode;
};

export const EditorMentionsProvider = observer(function EditorMentionsProvider(props: TEditorMentionsProviderProps) {
    const { children, projectId } = props;

    return (
        <EditorMentionsContext.Provider
            value={{
                projectId: projectId ?? undefined
            }}
        >
            {children}
        </EditorMentionsContext.Provider>
    );
});
