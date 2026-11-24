"use client";

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
  return (
    <div>
      <SettingsPageHeader
        title={t("General")}
        description={t(
          "Personalize your DrChenAI experience. Apply your preferences using the bar below.",
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
          title={t("Response language")}
          description={t(
            "Sets the default language for chat and capability responses.",
          )}
          control={
            <select
              aria-label={t("Response language")}
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
    </div>
  );
}
