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
            // oxlint-disable-next-line react/jsx-no-constructed-context-values
            value={{
                projectId: projectId ?? undefined
            }}
        >
            {children}
        </EditorMentionsContext.Provider>
    );
});
