"use client";

import { useCallback, type SetStateAction } from "react";
import { useTranslation } from "react-i18next";
import { APP_LANGUAGES, isAppLanguage, type AppLanguage } from "@/i18n/init";
import {
  SettingRow,
  SettingSection,
  SettingsPageHeader,
  selectClass,
  selectOptionClass,
} from "./shared";
import { RESPONSE_LANGUAGE_OPTIONS, useUiSettings } from "@/features/settings/store";
import { useStagedSettings } from "@/features/settings/store/useStagedSettings";
import { useUiLayout } from "@/hooks/useUiLayout";
import { UI_LAYOUTS, writeStoredUiLayout, type UiLayout } from "@/lib/ui-layout";

const UI_LAYOUT_LABELS: Record<UiLayout, string> = {
  classic: "Classic",
  modern: "Modern",
};

function LanguageSelect({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (next: AppLanguage) => void;
}) {
  const { t } = useTranslation();
  return (
    <select
      aria-label={label}
      className={`${selectClass} min-w-[200px]`}
      value={value}
      onChange={(event) => {
        const next = event.currentTarget.value;
        if (isAppLanguage(next)) onChange(next);
      }}
    >
      {APP_LANGUAGES.map(({ code, labelKey }) => (
        <option key={code} value={code} className={selectOptionClass}>
          {t(labelKey)}
        </option>
      ))}
    </select>
  );
}

export default function SettingsOverview() {
  const { t } = useTranslation();
  const { language, responseLanguage, updateLanguage, updateResponseLanguage } =
    useUiSettings();
  const uiLayout = useUiLayout();
  const setLiveUiLayout = useCallback(
    (action: SetStateAction<UiLayout>) =>
      writeStoredUiLayout(typeof action === "function" ? action(uiLayout) : action),
    [uiLayout],
  );
  const [stagedUiLayout, stageUiLayout] = useStagedSettings(
    "ui-layout",
    uiLayout,
    setLiveUiLayout,
  );
  return (
    <div>
      <SettingsPageHeader
        title={t("General")}
        description={t(
          "Make DeepTutor feel at home. Apply your preferences using the bar below.",
        )}
      />
      <SettingSection title={t("Language")}>
        <SettingRow
          title={t("Interface language")}
          description={t(
            "Controls navigation, settings, and status text only.",
          )}
          control={
            <LanguageSelect
              label={t("Interface language")}
              value={language}
              onChange={updateLanguage}
            />
          }
        />
        <SettingRow
          title={t("Model output language")}
          description={t(
            "Sets the default language for chat and capability responses.",
          )}
          control={
            <select
              aria-label={t("Model output language")}
              value={responseLanguage}
              onChange={(event) =>
                void updateResponseLanguage(
                  event.target.value as typeof responseLanguage,
                )
              }
              className={`${selectClass} min-w-[200px] pr-8`}
            >
              {RESPONSE_LANGUAGE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          }
        />
      </SettingSection>
      <SettingSection title={t("Layout")}>
        <SettingRow
          title={t("Interface layout")}
          description={t(
            "Classic keeps the familiar navigation; Modern is the redesigned interface.",
          )}
          control={
            <select
              aria-label={t("Interface layout")}
              value={stagedUiLayout}
              onChange={(event) => stageUiLayout(event.target.value as UiLayout)}
              className={`${selectClass} min-w-[200px] pr-8`}
            >
              {UI_LAYOUTS.map((layout) => (
                <option key={layout} value={layout} className={selectOptionClass}>
                  {t(UI_LAYOUT_LABELS[layout])}
                </option>
              ))}
            </select>
          }
        />
      </SettingSection>
    </div>
  );
}
