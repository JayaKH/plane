import { observer } from "mobx-react";
// helpers
import { cn } from "@plane/utils";

type Props = {
  id: string;
};

export const EditorPageMention = observer(function EditorPageMention(props: Props) {
  const { id } = props;

  return (
    <div className={cn("not-prose inline rounded-sm bg-accent-primary/20 px-1 py-0.5 text-accent-primary no-underline")} >
      @page({id})
    </div>
  );
});
