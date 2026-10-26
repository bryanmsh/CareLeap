import { useTranslation } from "react-i18next";

export function About() {
  const { t } = useTranslation();
  return (
    <>
      <p className="eyebrow">{t("design.aboutEyebrow")}</p>
      <h1>{t("about.title")}</h1>
      <p>{t("about.body")}</p>
      <p className="text-muted">{t("about.guardrail")}</p>
    </>
  );
}
