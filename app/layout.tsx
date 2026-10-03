import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata={title:"RedTraces AI — Threat Intelligence",description:"Unified threat intelligence across X, Facebook, Instagram, Telegram and dark-web forums.",icons:{icon:"/favicon.svg"},openGraph:{title:"RedTraces AI",description:"Threat intelligence for analyst review",images:["/favicon.svg"]},twitter:{card:"summary_large_image",title:"RedTraces AI",description:"Threat intelligence for analyst review",images:["/favicon.svg"]}};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
