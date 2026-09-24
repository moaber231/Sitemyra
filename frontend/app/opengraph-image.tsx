import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Sitemyra — Know when your competitors change.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px 80px",
          color: "#0f172a",
          backgroundColor: "#fafafa",
          backgroundImage:
            "radial-gradient(circle at 82% 14%, rgba(77,124,255,0.18), transparent 30%), radial-gradient(circle at 8% 88%, rgba(0,82,255,0.12), transparent 32%)",
          fontFamily: "Arial, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "18px" }}>
          <div
            style={{
              width: "62px",
              height: "62px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "18px",
              backgroundImage: "linear-gradient(135deg, #0052ff, #4d7cff)",
              color: "#ffffff",
              fontSize: "34px",
              fontWeight: 700,
            }}
          >
            S
          </div>
          <div style={{ fontSize: "32px", fontWeight: 700, letterSpacing: "-1px" }}>
            Sitemyra
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "22px" }}>
          <div
            style={{
              color: "#0052ff",
              fontSize: "18px",
              fontWeight: 700,
              letterSpacing: "3px",
              textTransform: "uppercase",
            }}
          >
            Competitor monitoring
          </div>
          <div
            style={{
              maxWidth: "900px",
              fontSize: "68px",
              lineHeight: 1.04,
              letterSpacing: "-3px",
              fontWeight: 700,
            }}
          >
            Know when your competitors change.
          </div>
          <div style={{ color: "#64748b", fontSize: "25px" }}>
            Pricing, pages, and content — monitored automatically.
          </div>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            color: "#64748b",
            fontSize: "20px",
          }}
        >
          <span>{siteUrl.replace(/^https?:\/\//, "").replace(/\/$/, "")}</span>
          <span style={{ color: "#0052ff" }}>Real product · Independent founder</span>
        </div>
      </div>
    ),
    size,
  );
}
