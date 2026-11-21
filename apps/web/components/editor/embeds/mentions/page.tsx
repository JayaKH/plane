import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { Link } from "react-router";
// plane imports
import { Logo } from "@plane/blocks/emoji-icon-picker";
import { PagesOutline } from "@makeplane/propel/icons";
import { Popover, PopoverContent, PopoverTrigger } from "@makeplane/propel/components/popover";
import { cn } from "@plane/utils";
// hooks
import { useEditorMentions } from "@/hooks/context/use-editor-mentions";
import { EPageStoreType, usePageStore } from "@/hooks/store/use-page-store";

type Props = {
  id: string;
};

export const EditorPageMention = observer(function EditorPageMention(props: Props) {
  const { id } = props;
  // router
  const { projectId: routerProjectId } = useParams();
  // params
  const { workspaceSlug } = useParams();
  // store hooks
  const { projectId: contextProjectId } = useEditorMentions();
  const pageStore = usePageStore(EPageStoreType.PROJECT);
  // derived values
  const projectId = contextProjectId ?? (routerProjectId as string | undefined);
  const pageDetails = pageStore.getPageById(id);
  const pageName = pageDetails?.name ?? "Unknown page";
  const pageLink = projectId ? `/${workspaceSlug}/projects/${projectId}/pages/${id}` : `/${workspaceSlug}/pages/${id}`;

  // Fetch the page from the store if not already loaded
  const [isLoaded, setIsLoaded] = useState(Boolean(pageDetails));
  useEffect(() => {
    // Already in store or required parameter is missing
    if (pageDetails || !workspaceSlug || !projectId) {
      setIsLoaded(true);
      return;
    }

    pageStore.fetchPageDetails(workspaceSlug, projectId, id, { trackVisit: false }).finally(() => setIsLoaded(true));
  }, [pageDetails, id, workspaceSlug, projectId]);

  if (!isLoaded) {
    return (
      <div className="not-prose inline rounded-sm bg-layer-1 px-1 py-0.5 text-tertiary no-underline">@loading...</div>
    );
  }

  if (!pageDetails) {
    return (
      <div className="not-prose inline rounded-sm bg-layer-1 px-1 py-0.5 text-tertiary no-underline">@Unknown page</div>
    );
  }

  return (
    <div
      className={cn(
        "not-prose inline rounded-sm bg-accent-subtle-active px-1 py-0.5 text-accent-primary no-underline",
        {
          "bg-label-indigo-bg text-label-indigo-text": id === pageDetails.id,
        }
      )}
    >
      <Popover>
        <PopoverTrigger openOnHover delay={100} nativeButton={false} render={<Link to={pageLink}>@{pageName}</Link>} />
        <PopoverContent variant="rich" side="bottom" align="start" sideOffset={8}>
          <div className="flex items-center gap-3">
            <div className="grid size-10 flex-shrink-0 place-items-center">
              {pageDetails.logo_props?.in_use ? (
                <Logo logo={pageDetails.logo_props} size={40} type="lucide" />
              ) : (
                <PagesOutline fontSize={40} />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <Link to={pageLink} className="not-prose block truncate text-body-xs-medium text-primary hover:underline">
                {pageName}
              </Link>
              <p className="truncate text-caption-sm-regular text-secondary">Page</p>
            </div>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
});
