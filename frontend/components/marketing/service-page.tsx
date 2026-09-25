"use client";

import Link from "next/link";
import {
  ArrowRight,
  CalendarClock,
  Check,
  Globe2,
  Mail,
  Palette,
  Phone,
  Search,
  Server,
  ShieldCheck,
  Sparkles,
  Wrench,
} from "lucide-react";
import { useEffect, useState } from "react";

import { MarketingShell } from "@/components/marketing/marketing-shell";
import { FOUNDER_PHONE, getPublicContactEmail } from "@/lib/site";

type Language = "en" | "el";

type Package = {
  name: string;
  price: string;
  description: string;
  features: string[];
  featured?: boolean;
};

type CarePlan = {
  name: string;
  price: string;
  description: string;
  features: string[];
};

const content = {
  en: {
    eyebrow: "Website construction",
    title: "Websites that look sharp and work hard.",
    intro:
      "I design and build modern websites shaped around your business — with a focus on appearance, speed, and the right experience on mobile and desktop.",
    primaryCta: "Discuss your project",
    secondaryCta: "View packages",
    packageEyebrow: "Website packages",
    packageTitle: "Choose the right starting point.",
    packageIntro:
      "Every project is shaped around the needs of the business. These are indicative starting prices; the final scope is agreed before work begins.",
    careEyebrow: "Monthly support",
    careTitle: "Keep the site useful after launch.",
    careIntro:
      "Optional monthly care for updates, small improvements, monitoring, and ongoing support.",
    hostingEyebrow: "Domain & hosting",
    hostingTitle: "One point of contact for the whole website.",
    hostingText:
      "I can also take care of the domain and hosting so you have one point of contact for the complete website. Final prices depend on the domain, hosting, and project needs.",
    noteTitle: "A clear starting point",
    noteText:
      "The prices above are indicative starting prices. Each website is designed around the needs of the business, and a detailed proposal is provided before the project starts. Prices do not include VAT where applicable.",
    contactTitle: "Have a project in mind?",
    contactText: "Send a short description of your business and what you want the website to do.",
    pillars: [
      { icon: Search, title: "Clear direction", text: "A focused structure around your customers and your offer." },
      { icon: Palette, title: "Custom design", text: "A visual identity that feels appropriate for your brand." },
      { icon: Wrench, title: "Reliable build", text: "Responsive pages, practical integrations, and thoughtful details." },
      { icon: ShieldCheck, title: "Ongoing care", text: "Updates, monitoring, and support when the site needs attention." },
    ],
    packages: [
      {
        name: "Starter",
        price: "from €650",
        description: "For small businesses that need a modern online presence.",
        features: [
          "Up to 5 pages",
          "Custom design",
          "Responsive design",
          "Homepage",
          "Services / menu",
          "Contact page",
          "Google Maps",
          "Social media integration",
          "Contact form",
          "Basic SEO",
          "Google Search Console",
          "Basic speed optimization",
        ],
        featured: false,
      },
      {
        name: "Business",
        price: "from €950",
        description: "For businesses that want a complete, more dynamic presence online.",
        features: [
          "Everything in Starter",
          "Up to 10 pages",
          "More custom UI/UX design",
          "Gallery / portfolio",
          "Advanced contact forms",
          "Booking / reservation integration",
          "Optimized SEO setup",
          "Google Business integration",
          "Analytics",
          "Animations and interactive elements",
          "Up to 2 revision rounds",
        ],
        featured: true,
      },
      {
        name: "Premium",
        price: "from €1,500",
        description: "For a fully customized digital presence.",
        features: [
          "Everything in Business",
          "Fully custom UI/UX",
          "10+ pages",
          "Advanced animations",
          "Advanced SEO setup",
          "Online booking / reservations",
          "Multilingual content",
          "Custom integrations",
          "Advanced forms and functionality",
          "Performance optimization",
          "Analytics and tracking setup",
          "Priority support",
        ],
        featured: false,
      },
    ] satisfies Package[],
    carePlans: [
      {
        name: "Care",
        price: "€35 / month",
        description: "For small, regular website upkeep.",
        features: ["Updates & security", "Backups", "Monitoring", "Small fixes", "Up to 30' of changes / month"],
      },
      {
        name: "Business Care",
        price: "€59 / month",
        description: "For a business that needs more regular attention.",
        features: ["Everything in Care", "Up to 1 hour of changes / month", "Text & photo updates", "Menu updates", "Small new sections", "Performance checks", "Priority support"],
      },
      {
        name: "Pro Care",
        price: "€120 / month",
        description: "For ongoing growth and technical support.",
        features: ["Everything in Business Care", "Up to 3 hours of work / month", "New pages & content", "Technical support", "SEO monitoring", "Analytics monitoring", "Priority service"],
      },
    ] satisfies CarePlan[],
  },
  el: {
    eyebrow: "Κατασκευή ιστοσελίδων",
    title: "Σύγχρονες, γρήγορες & επαγγελματικές ιστοσελίδες.",
    intro:
      "Σχεδιάζω και κατασκευάζω σύγχρονες ιστοσελίδες, προσαρμοσμένες στην εικόνα και τις ανάγκες της επιχείρησής σας — με έμφαση στην εμφάνιση, την ταχύτητα και τη σωστή εμπειρία σε κινητό και υπολογιστή.",
    primaryCta: "Συζητήστε το project σας",
    secondaryCta: "Δείτε τα πακέτα",
    packageEyebrow: "Πακέτα ιστοσελίδων",
    packageTitle: "Επιλέξτε το σωστό σημείο εκκίνησης.",
    packageIntro:
      "Κάθε project σχεδιάζεται γύρω από τις ανάγκες της επιχείρησης. Οι τιμές είναι ενδεικτικές τιμές εκκίνησης και η τελική έκταση συμφωνείται πριν ξεκινήσει η εργασία.",
    careEyebrow: "Μηνιαία υποστήριξη",
    careTitle: "Κρατήστε την ιστοσελίδα χρήσιμη μετά την ένταξη.",
    careIntro:
      "Προαιρετική μηνιαία υποστήριξη για ενημερώσεις, μικρές βελτιώσεις, monitoring και συνεχή βοήθεια.",
    hostingEyebrow: "Domain & hosting",
    hostingTitle: "Ένα σημείο επικοινωνίας για ολόκληρη την ιστοσελίδα.",
    hostingText:
      "Μπορώ επίσης να αναλάβω το domain και το hosting ώστε να έχετε ένα σημείο επικοινωνίας για ολόκληρη την ιστοσελίδα. Οι τελικές τιμές διαμορφώνονται ανάλογα με το domain, το hosting και τις ανάγκες του project.",
    noteTitle: "Μια ξεκάθαρη αρχή",
    noteText:
      "Οι παραπάνω τιμές είναι ενδεικτικές τιμές εκκίνησης. Κάθε website σχεδιάζεται σύμφωνα με τις ανάγκες της επιχείρησης και πριν την έναρξη παρέχεται αναλυτική προσφορά. Οι τιμές δεν περιλαμβάνουν ΦΠΑ, όπου εφαρμόζεται.",
    contactTitle: "Έχετε project στο μυαλό σας;",
    contactText: "Στείλτε μια σύντομη περιγραφή της επιχείρησης και του τι θέλετε να κάνει η ιστοσελίδα.",
    pillars: [
      { icon: Search, title: "Σαφής κατεύθυνση", text: "Σωστή δομή γύρω από τους πελάτες και την πρότασή σας." },
      { icon: Palette, title: "Custom design", text: "Οπτική ταυτότητα που ταιριάζει στο brand σας." },
      { icon: Wrench, title: "Αξιόπιστη κατασκευή", text: "Responsive σελίδες, πρακτικές ενσωματώσεις και προσεκτικές λεπτομέρειες." },
      { icon: ShieldCheck, title: "Συνεχής υποστήριξη", text: "Updates, monitoring και βοήθεια όταν χρειάζεται." },
    ],
    packages: [
      {
        name: "Starter",
        price: "από €650",
        description: "Για μικρές επιχειρήσεις που χρειάζονται μια σύγχρονη online παρουσία.",
        features: ["Έως 5 σελίδες", "Custom design", "Responsive σχεδιασμός", "Αρχική σελίδα", "Υπηρεσίες / Menu", "Σελίδα επικοινωνίας", "Google Maps", "Social Media integration", "Contact form", "Βασικό SEO", "Google Search Console", "Βασική βελτιστοποίηση ταχύτητας"],
        featured: false,
      },
      {
        name: "Business",
        price: "από €950",
        description: "Για επιχειρήσεις που θέλουν ολοκληρωμένη και πιο δυναμική παρουσία στο διαδίκτυο.",
        features: ["Όλα τα χαρακτηριστικά του Starter", "Έως 10 σελίδες", "Πιο custom UI/UX σχεδιασμός", "Gallery / Portfolio", "Advanced contact forms", "Booking / Reservation integration", "Βελτιστοποιημένο SEO setup", "Google Business integration", "Analytics", "Animations & interactive στοιχεία", "Έως 2 γύροι διορθώσεων"],
        featured: true,
      },
      {
        name: "Premium",
        price: "από €1.500",
        description: "Για επιχειρήσεις που θέλουν μια πλήρως εξατομικευμένη ψηφιακή παρουσία.",
        features: ["Όλα τα χαρακτηριστικά του Business", "Πλήρως custom UI/UX", "10+ σελίδες", "Advanced animations", "Advanced SEO setup", "Online booking / reservations", "Πολυγλωσσικό περιεχόμενο", "Custom integrations", "Advanced forms & λειτουργίες", "Performance optimization", "Analytics & tracking setup", "Προτεραιότητα στην υποστήριξη"],
        featured: false,
      },
    ] satisfies Package[],
    carePlans: [
      { name: "Care", price: "€35 / μήνα", description: "Για μικρές, τακτικές εργασίες συντήρησης.", features: ["Updates & security", "Backups", "Monitoring", "Μικρές διορθώσεις", "Έως 30' αλλαγών / μήνα"] },
      { name: "Business Care", price: "€59 / μήνα", description: "Για επιχείρηση που χρειάζεται πιο τακτική προσοχή.", features: ["Όλα του CARE", "Έως 1 ώρα αλλαγών / μήνα", "Κείμενα & φωτογραφίες", "Menu updates", "Μικρές νέες ενότητες", "Performance checks", "Priority support"] },
      { name: "Pro Care", price: "€120 / μήνα", description: "Για συνεχή ανάπτυξη και τεχνική υποστήριξη.", features: ["Όλα του BUSINESS CARE", "Έως 3 ώρες εργασίας / μήνα", "Νέες σελίδες & περιεχόμενο", "Technical support", "SEO monitoring", "Analytics monitoring", "Προτεραιότητα εξυπηρέτησης"] },
    ] satisfies CarePlan[],
  },
} as const;

export function ServicePage() {
  const [language, setLanguage] = useState<Language>("en");
  const copy = content[language];
  const email = getPublicContactEmail();

  useEffect(() => {
    const saved = window.localStorage.getItem("sitemyra-service-language");
    if (saved === "en" || saved === "el") setLanguage(saved);
  }, []);

  function toggleLanguage() {
    const next = language === "en" ? "el" : "en";
    setLanguage(next);
    window.localStorage.setItem("sitemyra-service-language", next);
  }

  return (
    <MarketingShell>
      <div lang={language}>
        <section className="marketing-noise relative overflow-hidden border-b border-border px-5 pb-20 pt-16 sm:px-6 sm:pt-24 lg:px-8 lg:pb-28">
          <div className="marketing-orb" aria-hidden="true" />
          <div className="relative mx-auto max-w-6xl">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="section-label">
                <span aria-hidden="true" />
                {copy.eyebrow}
              </div>
              <LanguageToggle language={language} onToggle={toggleLanguage} />
            </div>
            <div className="mt-8 grid gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-end">
              <div>
                <h1 className="marketing-display max-w-4xl text-[clamp(3rem,7vw,5.5rem)]">
                  {copy.title}
                </h1>
                <p className="marketing-body-large mt-7 max-w-2xl text-muted-foreground">
                  {copy.intro}
                </p>
                <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                  <a
                    href={`mailto:${email}?subject=${encodeURIComponent("Website project")}`}
                    className="apeiro-btn apeiro-btn-primary"
                  >
                    {copy.primaryCta}
                    <ArrowRight size={16} aria-hidden="true" />
                  </a>
                  <a href="#packages" className="apeiro-btn apeiro-btn-outline">
                    {copy.secondaryCta}
                  </a>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                {copy.pillars.map((pillar) => (
                  <div key={pillar.title} className="flex gap-3 rounded-2xl border border-border bg-card/80 p-4 shadow-sm backdrop-blur">
                    <span className="modern-icon h-9 w-9 shrink-0 rounded-lg">
                      <pillar.icon size={17} strokeWidth={1.7} aria-hidden="true" />
                    </span>
                    <div>
                      <h2 className="text-sm font-semibold text-foreground">{pillar.title}</h2>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">{pillar.text}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section id="packages" className="marketing-grid scroll-mt-24 border-b border-border px-5 py-24 sm:px-6 md:py-32 lg:px-8">
          <div className="mx-auto max-w-6xl">
            <div className="max-w-3xl">
              <div className="section-label"><span aria-hidden="true" />{copy.packageEyebrow}</div>
              <h2 className="mt-5 text-4xl sm:text-6xl">{copy.packageTitle}</h2>
              <p className="mt-5 text-base leading-7 text-muted-foreground">{copy.packageIntro}</p>
            </div>
            <div className="mt-14 grid items-stretch gap-5 lg:grid-cols-3">
              {copy.packages.map((item) => (
                <article key={item.name} className={`group rounded-2xl p-[2px] transition duration-300 hover:-translate-y-1 ${item.featured ? "bg-gradient-to-br from-accent via-accent-secondary to-accent shadow-[0_18px_42px_rgb(0_82_255_/_0.2)] lg:-translate-y-4" : "border border-border bg-card shadow-sm"}`}>
                  <div className="flex h-full flex-col rounded-[calc(1rem-2px)] bg-card p-6 sm:p-8">
                    <div className="flex items-center justify-between gap-3 border-b border-border pb-5">
                      <h3 className="font-mono text-sm font-semibold uppercase tracking-[0.14em]">{item.name}</h3>
                      {item.featured ? <span className="rounded-full border border-accent/20 bg-accent/5 px-2.5 py-1 font-mono text-[0.62rem] uppercase tracking-[0.12em] text-accent">{language === "en" ? "Popular" : "Δημοφιλές"}</span> : null}
                    </div>
                    <p className="mt-7 text-4xl font-semibold tracking-tight text-foreground">{item.price}</p>
                    <p className="mt-4 min-h-16 text-sm leading-6 text-muted-foreground">{item.description}</p>
                    <ul className="mt-8 flex-1 space-y-3 border-t border-border pt-6 text-sm text-foreground">
                      {item.features.map((feature) => <li key={feature} className="flex items-start gap-3"><span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent/10 text-accent"><Check size={13} strokeWidth={2.2} aria-hidden="true" /></span>{feature}</li>)}
                    </ul>
                    <a href={`mailto:${email}?subject=${encodeURIComponent(`${item.name} website package`)}`} className={`apeiro-btn mt-9 w-full ${item.featured ? "apeiro-btn-primary" : "apeiro-btn-outline"}`}>
                      {language === "en" ? "Ask about this package" : "Ρωτήστε για αυτό το πακέτο"}
                      <ArrowRight size={15} aria-hidden="true" />
                    </a>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="border-b border-border px-5 py-24 sm:px-6 md:py-32 lg:px-8">
          <div className="mx-auto max-w-6xl">
            <div className="max-w-3xl">
              <div className="section-label"><span aria-hidden="true" />{copy.careEyebrow}</div>
              <h2 className="mt-5 text-4xl sm:text-6xl">{copy.careTitle}</h2>
              <p className="mt-5 text-base leading-7 text-muted-foreground">{copy.careIntro}</p>
            </div>
            <div className="mt-14 grid gap-5 lg:grid-cols-3">
              {copy.carePlans.map((plan) => (
                <article key={plan.name} className="rounded-2xl border border-border bg-card p-6 shadow-sm transition duration-300 hover:-translate-y-1 hover:border-accent/30 hover:shadow-lg sm:p-8">
                  <div className="flex items-center justify-between gap-3"><h3 className="font-mono text-sm font-semibold uppercase tracking-[0.14em]">{plan.name}</h3><CalendarClock size={19} className="text-accent" aria-hidden="true" /></div>
                  <p className="mt-6 text-3xl font-semibold tracking-tight text-foreground">{plan.price}</p>
                  <p className="mt-3 text-sm leading-6 text-muted-foreground">{plan.description}</p>
                  <ul className="mt-7 space-y-3 border-t border-border pt-6 text-sm text-foreground">
                    {plan.features.map((feature) => <li key={feature} className="flex items-start gap-3"><Check size={15} className="mt-0.5 shrink-0 text-accent" aria-hidden="true" />{feature}</li>)}
                  </ul>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="marketing-inverted px-5 py-24 sm:px-6 md:py-32 lg:px-8">
          <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
            <div>
              <div className="section-label section-label--dark"><span aria-hidden="true" />{copy.hostingEyebrow}</div>
              <h2 className="mt-5 text-4xl text-white sm:text-6xl">{copy.hostingTitle}</h2>
            </div>
            <div className="rounded-2xl border border-white/15 bg-white/5 p-6 backdrop-blur sm:p-8">
              <Server size={24} className="text-blue-300" aria-hidden="true" />
              <p className="mt-5 text-lg leading-8 text-slate-200">{copy.hostingText}</p>
            </div>
          </div>
        </section>

        <section className="px-5 py-20 sm:px-6 md:py-28 lg:px-8">
          <div className="mx-auto max-w-4xl rounded-3xl border border-border bg-card p-6 shadow-sm sm:p-10">
            <div className="flex gap-4"><span className="modern-icon h-11 w-11 shrink-0 rounded-xl"><Sparkles size={20} aria-hidden="true" /></span><div><h2 className="text-2xl text-foreground">{copy.noteTitle}</h2><p className="mt-3 text-sm leading-7 text-muted-foreground">{copy.noteText}</p></div></div>
            <div className="mt-8 flex flex-col gap-3 border-t border-border pt-6 sm:flex-row sm:flex-wrap">
              <a href={`mailto:${email}`} className="apeiro-btn apeiro-btn-primary"><Mail size={16} aria-hidden="true" />{email}</a>
              <a href={`tel:${FOUNDER_PHONE.replace(/\s/g, "")}`} className="apeiro-btn apeiro-btn-outline"><Phone size={16} aria-hidden="true" />{FOUNDER_PHONE}</a>
            </div>
          </div>
        </section>

        <section className="marketing-noise border-t border-border px-5 py-24 text-center sm:px-6 md:py-32 lg:px-8">
          <div className="mx-auto max-w-3xl">
            <div className="section-label mx-auto"><span aria-hidden="true" />{copy.contactTitle}</div>
            <h2 className="mt-6 text-4xl sm:text-6xl">{copy.contactText}</h2>
            <a href={`mailto:${email}?subject=${encodeURIComponent("Website project")}`} className="apeiro-btn apeiro-btn-primary mt-8">{copy.primaryCta}<ArrowRight size={16} aria-hidden="true" /></a>
          </div>
        </section>
      </div>
    </MarketingShell>
  );
}

function LanguageToggle({ language, onToggle }: { language: Language; onToggle: () => void }) {
  return (
    <button type="button" onClick={onToggle} aria-label={language === "en" ? "Switch to Greek" : "Switch to English"} className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-3 py-2 font-mono text-[0.68rem] font-semibold uppercase tracking-[0.12em] text-muted-foreground shadow-sm transition hover:border-accent/30 hover:text-accent">
      <span className={language === "en" ? "text-accent" : ""}>EN</span>
      <span aria-hidden="true">/</span>
      <span className={language === "el" ? "text-accent" : ""}>ΕΛ</span>
    </button>
  );
}
