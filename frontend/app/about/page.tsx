import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Award,
  BriefcaseBusiness,
  CheckCircle2,
  Code2,
  ExternalLink,
  GraduationCap,
  Mail,
  Phone,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import { MarketingShell } from "@/components/marketing/marketing-shell";
import { StructuredData } from "@/components/marketing/structured-data";
import {
  FOUNDER_LINKS,
  FOUNDER_PHONE,
  getPublicContactEmail,
} from "@/lib/site";
import { marketingMetadata } from "@/lib/marketing-seo";

export const metadata = marketingMetadata({
  title: "About Konstantinos and Sitemyra",
  description:
    "Meet Konstantinos Gkogkos, the software engineer and cybersecurity professional building Sitemyra and offering custom website construction.",
  path: "/about",
});

const experience = [
  {
    period: "Nov 2025 – Sep 2026",
    role: "Cybersecurity Team Member (Cyberlabs)",
    company: "NATO Rapid Deployable Corps – Greece (NRDC-GR)",
    points: [
      "Performed vulnerability assessments and system hardening across simulated infrastructures.",
      "Applied defensive security techniques to mitigate attack vectors and improve resilience.",
      "Improved overall security posture by 30% through testing and remediation.",
    ],
  },
  {
    period: "Jan 2024 – Aug 2025",
    role: "Software Engineering Intern (Thesis Project)",
    company: "ICS-FORTH",
    points: [
      "Developed a secure configuration platform using Java and PostgreSQL for Synthesis-Core.",
      "Implemented data validation and handling mechanisms, increasing configuration efficiency by 40%.",
      "Received a Letter of Recommendation for technical performance and contribution.",
    ],
  },
  {
    period: "Sep 2023 – Dec 2023",
    role: "Backend Developer Intern",
    company: "QRealm",
    points: [
      "Built Django backend services with emphasis on secure data handling and API design.",
      "Optimized relational database queries, improving performance by 25%.",
    ],
  },
];

const projects = [
  {
    title: "Compiler for Alpha Language",
    stack: "C · Flex · Bison",
    text: "Developed a full compiler covering lexical, syntax, semantic analysis and IR generation.",
  },
  {
    title: "Biomedical IR System",
    stack: "Information retrieval",
    text: "Designed a search engine with optimized ranking algorithms, achieving 35% higher relevance.",
  },
  {
    title: "Stratego Board Game",
    stack: "Java",
    text: "Developed a fully playable Java game using OOP, game-state management and move validation.",
  },
  {
    title: "Car Rental System",
    stack: "Java · SQL · JDBC",
    text: "Built a database-driven rental system with booking, user management and rental tracking.",
  },
];

const skillGroups = [
  { title: "Languages", items: ["C", "C++", "Java", "Python"] },
  { title: "Tools", items: ["Git", "Docker", "Postman", "PgAdmin", "Django"] },
  { title: "Security", items: ["Wireshark", "Nmap", "Burp Suite"] },
  { title: "Core", items: ["Algorithms", "Systems Programming", "OOP", "Cybersecurity", "Secure Coding"] },
];

export default function AboutPage() {
  const email = getPublicContactEmail();

  return (
    <MarketingShell>
      <StructuredData />

      <section className="marketing-noise relative overflow-hidden border-b border-border px-5 pb-20 pt-16 sm:px-6 sm:pt-24 lg:px-8 lg:pb-28">
        <div className="marketing-orb" aria-hidden="true" />
        <div className="relative mx-auto max-w-6xl">
          <div className="section-label"><span aria-hidden="true" />About the founder</div>
          <div className="mt-8 grid gap-12 lg:grid-cols-[1.1fr_0.9fr] lg:items-end">
            <div>
              <h1 className="marketing-display max-w-4xl text-[clamp(3.25rem,7vw,5.75rem)]">
                Software with a <span className="gradient-text">purpose.</span>
              </h1>
              <p className="marketing-body-large mt-7 max-w-2xl text-muted-foreground">
                Konstantinos Gkogkos is a software engineer, cybersecurity
                professional, and independent builder based in Greece. He combines
                secure systems thinking with a practical eye for useful digital
                products.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link href="/services" className="apeiro-btn apeiro-btn-primary">
                  Work with me
                  <ArrowRight size={16} aria-hidden="true" />
                </Link>
                <a href={`mailto:${email}`} className="apeiro-btn apeiro-btn-outline">
                  <Mail size={16} aria-hidden="true" />
                  Contact Konstantinos
                </a>
              </div>
            </div>
            <div className="rounded-3xl border border-accent/20 bg-card p-3 shadow-xl">
              <div className="relative aspect-[4/5] overflow-hidden rounded-2xl bg-muted">
                <Image
                  src="/images/konstantinos-gkogkos.jpg"
                  alt="Konstantinos Gkogkos"
                  fill
                  priority
                  sizes="(max-width: 1024px) 90vw, 420px"
                  className="object-cover object-top"
                />
              </div>
              <div className="flex items-center justify-between gap-3 px-2 pb-1 pt-4">
                <div>
                  <p className="font-semibold text-foreground">Konstantinos Gkogkos</p>
                  <p className="mt-1 text-xs text-muted-foreground">Founder · Engineer · Builder</p>
                </div>
                <span className="modern-icon h-10 w-10 rounded-xl"><Code2 size={18} aria-hidden="true" /></span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="marketing-inverted px-5 py-20 sm:px-6 md:py-28 lg:px-8" aria-labelledby="contact-heading">
        <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
          <div>
            <div className="section-label section-label--dark"><span aria-hidden="true" />The work behind the work</div>
            <h2 id="contact-heading" className="mt-5 text-4xl text-white sm:text-6xl">Engineering, security, and a bias toward clarity.</h2>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-2xl border border-white/15 bg-white/5 p-5 backdrop-blur">
              <ShieldCheck size={21} className="text-blue-300" aria-hidden="true" />
              <h3 className="mt-5 text-lg text-white">Secure by default</h3>
              <p className="mt-2 text-sm leading-6 text-slate-300">Security assessments, secure coding, and resilient systems are part of the background, not an afterthought.</p>
            </div>
            <div className="rounded-2xl border border-white/15 bg-white/5 p-5 backdrop-blur">
              <Sparkles size={21} className="text-blue-300" aria-hidden="true" />
              <h3 className="mt-5 text-lg text-white">Useful by design</h3>
              <p className="mt-2 text-sm leading-6 text-slate-300">Sitemyra and every website project start with the user problem and end with something clear enough to use.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="px-5 py-20 sm:px-6 md:py-28 lg:px-8" aria-labelledby="experience-heading">
        <div className="mx-auto max-w-6xl">
          <div className="max-w-3xl">
            <div className="section-label"><span aria-hidden="true" />Experience</div>
            <h2 id="experience-heading" className="mt-5 text-4xl sm:text-6xl">Building, testing, and improving real systems.</h2>
          </div>
          <div className="mt-14 grid gap-5">
            {experience.map((item) => (
              <article key={`${item.company}-${item.role}`} className="grid gap-5 rounded-2xl border border-border bg-card p-6 shadow-sm transition hover:border-accent/30 hover:shadow-lg sm:p-8 lg:grid-cols-[10rem_1fr]">
                <div>
                  <span className="font-mono text-xs uppercase tracking-[0.1em] text-accent">{item.period}</span>
                  <BriefcaseBusiness size={19} className="mt-4 text-muted-foreground" aria-hidden="true" />
                </div>
                <div>
                  <h3 className="text-2xl text-foreground">{item.role}</h3>
                  <p className="mt-1 font-semibold text-accent">{item.company}</p>
                  <ul className="mt-5 space-y-3 text-sm leading-6 text-muted-foreground">
                    {item.points.map((point) => <li key={point} className="flex gap-3"><CheckCircle2 size={16} className="mt-1 shrink-0 text-success" aria-hidden="true" />{point}</li>)}
                  </ul>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="marketing-grid border-y border-border px-5 py-20 sm:px-6 md:py-28 lg:px-8" aria-labelledby="education-heading">
        <div className="mx-auto max-w-6xl">
          <div className="max-w-3xl">
            <div className="section-label"><span aria-hidden="true" />Education</div>
            <h2 id="education-heading" className="mt-5 text-4xl sm:text-6xl">A technical foundation with academic depth.</h2>
          </div>
          <div className="mt-14 grid gap-5 lg:grid-cols-2">
            <article className="rounded-2xl border border-border bg-card p-6 shadow-sm sm:p-8">
              <div className="flex items-start justify-between gap-4"><span className="modern-icon h-11 w-11 rounded-xl"><GraduationCap size={20} aria-hidden="true" /></span><span className="rounded-full bg-accent/10 px-2.5 py-1 font-mono text-[0.65rem] uppercase tracking-[0.1em] text-accent">Present</span></div>
              <h3 className="mt-8 text-2xl text-foreground">M.Sc. in Artificial Intelligence</h3>
              <p className="mt-2 font-semibold text-foreground">Aristotle University of Thessaloniki (AUTH)</p>
              <div className="mt-6 grid gap-3 border-t border-border pt-5 text-sm text-muted-foreground sm:grid-cols-2"><p><strong className="text-foreground">June 2025</strong><br />Started programme</p><p><strong className="text-foreground">8.68 / 10</strong><br />Grade</p><p><strong className="text-foreground">3rd / 300</strong><br />Selected candidate</p><p><strong className="text-foreground">AI</strong><br />Focus area</p></div>
            </article>
            <article className="rounded-2xl border border-border bg-card p-6 shadow-sm sm:p-8">
              <div className="flex items-start justify-between gap-4"><span className="modern-icon h-11 w-11 rounded-xl"><GraduationCap size={20} aria-hidden="true" /></span><span className="rounded-full bg-muted px-2.5 py-1 font-mono text-[0.65rem] uppercase tracking-[0.1em] text-muted-foreground">2024 – 2025</span></div>
              <h3 className="mt-8 text-2xl text-foreground">B.Sc. in Computer Science</h3>
              <p className="mt-2 font-semibold text-foreground">University of Crete</p>
              <p className="mt-6 border-t border-border pt-5 text-sm leading-6 text-muted-foreground">Undergraduate Scholarship (2024–2025) at ICS-FORTH.</p>
            </article>
          </div>
        </div>
      </section>

      <section className="px-5 py-20 sm:px-6 md:py-28 lg:px-8" aria-labelledby="projects-heading">
        <div className="mx-auto max-w-6xl">
          <div className="max-w-3xl">
            <div className="section-label"><span aria-hidden="true" />Selected projects</div>
            <h2 id="projects-heading" className="mt-5 text-4xl sm:text-6xl">Systems, languages, and useful experiments.</h2>
          </div>
          <div className="mt-14 grid gap-5 sm:grid-cols-2">
            {projects.map((project) => (
              <article key={project.title} className="group rounded-2xl border border-border bg-card p-6 shadow-sm transition hover:-translate-y-1 hover:border-accent/30 hover:shadow-lg sm:p-8">
                <div className="flex items-start justify-between gap-4"><span className="modern-icon h-10 w-10 rounded-xl"><Code2 size={18} aria-hidden="true" /></span><span className="font-mono text-[0.65rem] uppercase tracking-[0.1em] text-muted-foreground">{project.stack}</span></div>
                <h3 className="mt-8 text-2xl text-foreground">{project.title}</h3>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">{project.text}</p>
                <a href={FOUNDER_LINKS[0].href} target="_blank" rel="noopener noreferrer" className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-accent underline underline-offset-4">View GitHub profile<ArrowUpRight size={15} aria-hidden="true" /></a>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="marketing-grid border-y border-border px-5 py-20 sm:px-6 md:py-28 lg:px-8" aria-labelledby="skills-heading">
        <div className="mx-auto max-w-6xl">
          <div className="max-w-3xl"><div className="section-label"><span aria-hidden="true" />Skills & additional</div><h2 id="skills-heading" className="mt-5 text-4xl sm:text-6xl">A practical toolkit.</h2></div>
          <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {skillGroups.map((group) => <div key={group.title} className="rounded-2xl border border-border bg-card p-6 shadow-sm"><h3 className="font-mono text-xs uppercase tracking-[0.12em] text-accent">{group.title}</h3><div className="mt-5 flex flex-wrap gap-2">{group.items.map((item) => <span key={item} className="rounded-full border border-border bg-muted px-3 py-1.5 text-xs text-foreground">{item}</span>)}</div></div>)}
          </div>
          <div className="mt-5 grid gap-5 sm:grid-cols-2"><div className="flex gap-4 rounded-2xl border border-border bg-card p-6"><Award size={21} className="shrink-0 text-accent" aria-hidden="true" /><div><h3 className="font-semibold">Military Service</h3><p className="mt-1 text-sm text-muted-foreground">Completed.</p></div></div><div className="flex gap-4 rounded-2xl border border-border bg-card p-6"><GraduationCap size={21} className="shrink-0 text-accent" aria-hidden="true" /><div><h3 className="font-semibold">Undergraduate Scholarship</h3><p className="mt-1 text-sm text-muted-foreground">ICS-FORTH · 2024–2025.</p></div></div></div>
        </div>
      </section>

      <section className="marketing-inverted px-5 py-20 sm:px-6 md:py-28 lg:px-8" aria-labelledby="founder-contact-heading">
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-12 lg:grid-cols-[1fr_0.85fr] lg:items-center">
            <div><div className="section-label section-label--dark"><span aria-hidden="true" />Get in touch</div><h2 id="founder-contact-heading" className="mt-5 text-4xl text-white sm:text-6xl">Have a question, a project, or an idea?</h2><p className="mt-6 max-w-xl text-lg leading-8 text-slate-300">The fastest way to reach Konstantinos is email. For a website brief, include the business type, the pages you need, and your timeline.</p></div>
            <div className="rounded-2xl border border-white/15 bg-white/5 p-6 backdrop-blur sm:p-8">
              <div className="grid gap-3">
                <a href={`mailto:${email}`} className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 p-4 text-white transition hover:bg-white/10"><Mail size={18} className="text-blue-300" aria-hidden="true" /><span className="break-all text-sm">{email}</span></a>
                <a href={`tel:${FOUNDER_PHONE.replace(/\s/g, "")}`} className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 p-4 text-white transition hover:bg-white/10"><Phone size={18} className="text-blue-300" aria-hidden="true" /><span className="text-sm">{FOUNDER_PHONE}</span></a>
                {FOUNDER_LINKS.map((item) => <a key={item.href} href={item.href} target="_blank" rel="noopener noreferrer" className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-white transition hover:bg-white/10"><span>{item.label}</span><ExternalLink size={16} className="text-blue-300" aria-hidden="true" /></a>)}
              </div>
            </div>
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}
