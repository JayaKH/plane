/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback } from "react";
// plane editor
import { Avatar } from "@makeplane/propel/components/avatar";
import { Logo } from "@plane/blocks/emoji-icon-picker";
import { PagesOutline } from "@makeplane/propel/icons";
import type { TMentionSection, TMentionSuggestion } from "@plane/editor";
// plane types
import type {
  TSearchEntities,
  TSearchEntityRequestPayload,
  TSearchResponse,
  TUserSearchResponse,
  TPageSearchResponse,
} from "@plane/types";
// helpers
import { getFileURL } from "@plane/utils";
// plane web hooks
import { useAdditionalEditorMention } from "@/hooks/use-additional-editor-mention";

type TArgs = {
  enableAdvancedMentions?: boolean;
  searchEntity: (payload: TSearchEntityRequestPayload) => Promise<TSearchResponse>;
};

export const useEditorMention = (args: TArgs) => {
  const { enableAdvancedMentions = false, searchEntity } = args;
  // additional mentions
  const { editorMentionTypes, updateAdditionalSections } = useAdditionalEditorMention({
    enableAdvancedMentions,
  });
  // fetch mentions handler
  const fetchMentions = useCallback(
    async (query: string): Promise<TMentionSection[]> => {
      try {
        const res = await searchEntity({
          count: 5,
          query_type: editorMentionTypes,
          query,
        });
        const suggestionSections: TMentionSection[] = [];
        if (!res) {
          throw new Error("No response found");
        }
        Object.keys(res).map((key) => {
          const responseKey = key as TSearchEntities;
          const response = res[responseKey];
          if (response && response.length > 0) {
            if (responseKey === "user_mention") {
              const items: TMentionSuggestion[] = (response as TUserSearchResponse[]).map((user) => ({
                icon: (
                  <Avatar
                    alt={user.member__display_name}
                    fallback={user.member__display_name?.[0]?.toUpperCase()}
                    src={getFileURL(user.member__avatar_url)}
                    size="xs"
                  />
                ),
                id: user.member__id,
                entity_identifier: user.member__id,
                entity_name: "user_mention",
                title: user.member__display_name,
              }));
              suggestionSections.push({
                key: "users",
                title: "Users",
                items,
              });
            } else if (responseKey === "page") {
              const items: TMentionSuggestion[] = (response as TPageSearchResponse[])
                .filter((page) => page.id)
                .map((page) => ({
                  icon: page.logo_props?.in_use ? (
                    <Logo logo={page.logo_props} size={40} type="lucide" />
                  ) : (
                    <PagesOutline fontSize={40} />
                  ),
                  id: page.id!,
                  entity_identifier: page.id!,
                  entity_name: "page",
                  title: page.name ?? "Unknown page",
                }));
              suggestionSections.push({
                key: "pages",
                title: "Pages",
                items,
              });
            }
          }
        });
        const { sections } = updateAdditionalSections({
          response: res,
        });
        return [...suggestionSections, ...sections];
      } catch (error) {
        console.error("Error in fetching mentions:", error);
        throw error;
      }
    },
    [editorMentionTypes, searchEntity, updateAdditionalSections]
  );

  return {
    fetchMentions,
  };
};
