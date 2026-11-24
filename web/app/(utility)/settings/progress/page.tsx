"use client";

import { FeaturePage, PageHeader } from '@/components/layout/FeaturePage'
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  listLearningRecords,
  type LearningRecords,
} from "@/lib/learning-records-api";
import { listReadingLibraryMaterials } from "@/lib/reading-workspace-api";

function percent(value: number): number {
  return Math.round(value * 100);
}

export default function LearningProgressPage() {
  const { t } = useTranslation();
  const [records, setRecords] = useState<LearningRecords | null>(null);
  const [materialTitles, setMaterialTitles] = useState<Record<string, string>>({});
  const [error, setError] = useState(false);

  useEffect(() => {
    void listLearningRecords().then(setRecords).catch(() => setError(true));
    void listReadingLibraryMaterials()
      .then(({ materials }) =>
        setMaterialTitles(
          Object.fromEntries(materials.map((material) => [material.material_id, material.title])),
        ),
      )
      .catch(() => {
        // Progress remains usable if the library catalogue is unavailable.
      });
  }, []);

  const progress = records?.progress ?? [];
  const activities = records?.activities ?? [];


  return (
    <FeaturePage>
      <PageHeader title={t("Learning progress")} description={t("Track your learning journey, reading progress, and recent activities.")} />
      {error ? (
        <p className="mt-8 text-sm text-red-600">{t("Unable to load learning progress")}</p>
      ) : records === null ? (
        <p className="mt-8 text-sm text-[var(--muted-foreground)]">{t("Loading progress")}</p>
      ) : (
        <>
          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
              <span className="block text-xs text-[var(--muted-foreground)]">{t("Reading materials")}</span>
              <strong className="mt-2 block text-3xl font-semibold tracking-tight">{progress.length}</strong>
            </div>
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
              <span className="block text-xs text-[var(--muted-foreground)]">{t("Learning activity")}</span>
              <strong className="mt-2 block text-3xl font-semibold tracking-tight">{activities.length}</strong>
            </div>
          </div>
          <section className="mt-6">
            <h2 className="text-sm font-semibold">{t("Reading progress")}</h2>
            {progress.length === 0 ? (
              <p className="mt-3 text-sm text-[var(--muted-foreground)]">{t("Start reading a learning material to track your progress here.")}</p>
            ) : (
              <ul className="mt-3 grid gap-3">
                {progress.map((record) => (
                  <li key={record.material_id} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
                    <div className="flex items-center justify-between gap-3">
                      <span className="min-w-0 truncate font-medium">{materialTitles[record.material_id] || record.material_id}</span>
                      <span className="text-xs text-[var(--muted-foreground)]">
                        {percent(record.furthest_percentage)}%
                      </span>
                    </div>
                    <div
                      className="mt-4 h-2 overflow-hidden rounded-full bg-[var(--border)]"
                      role="progressbar"
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={percent(record.furthest_percentage)}
                      aria-label={t("Furthest reading progress")}
                    >
                      <div
                        className="h-full rounded-full bg-[var(--primary)]"
                        style={{ width: `${Math.min(100, Math.max(0, percent(record.furthest_percentage)))}%` }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section className="mt-6">
            <h2 className="text-sm font-semibold">{t("Learning activity")}</h2>
            {activities.length === 0 ? (
              <p className="mt-3 text-sm text-[var(--muted-foreground)]">{t("Your recent learning activities will appear here.")}</p>
            ) : (
              <ul className="mt-3 grid gap-3">
                {activities.map((record) => (
                  <li key={record.activity_id} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
                    <span className="font-medium">{materialTitles[record.material_id] || record.material_id}</span>
                    <span className="mt-1 block text-xs text-[var(--muted-foreground)]">
                      {record.action} · {record.extension_id} · {t("Locator")} {record.locator}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </FeaturePage>
  );
}
