"use client";
import { useEffect, useRef, useState } from "react";

const ease = "cubic-bezier(.22,1,.36,1)";
export function useAgencyMotion(view: string, ready: boolean, busy: boolean, enabled: boolean) {
  const seen = useRef(new WeakSet<Element>());
  const navSeen = useRef(false);
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const q = matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(q.matches);
    update(); q.addEventListener("change", update);
    return () => q.removeEventListener("change", update);
  }, []);
  const active = enabled && !reduced;
  useEffect(() => {
    if (!ready || busy) return;
    const animations: Animation[] = [];
    const animate = (el: Element, frames: Keyframe[], delay = 0, duration = 600) => {
      if (!active || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      animations.push(el.animate(frames, {duration, delay, easing: ease, fill: "backwards"}));
    };
    const rise = [{opacity:0,transform:"translateY(30px)"},{opacity:1,transform:"translateY(0)"}];
    const page = document.querySelector(".rt-view");
    if (page && view !== "overview") animate(page,[{opacity:0,transform:"translateY(10px)"},{opacity:1,transform:"translateY(0)"}],0,350);
    const nav = document.querySelector(".rt-topbar");
    if (nav && !navSeen.current) {
      animate(nav,[{opacity:0,transform:"translateY(-12px)"},{opacity:1,transform:"translateY(0)"}],0,500);
      navSeen.current = true;
    }
    document.querySelectorAll(".rt-hero-line").forEach((el,i) => {
      if (seen.current.has(el)) return;
      animate(el,rise,100+i*100,700); seen.current.add(el);
    });
    [".rt-hero-description",".rt-hero-actions",".rt-hero-meta"].forEach((s,i) => {
      const el=document.querySelector(s); if(!el || seen.current.has(el)) return;
      animate(el,rise,320+i*90); seen.current.add(el);
    });
    const art=document.querySelector(".rt-portrait-reveal");
    if(art && !seen.current.has(art)) {
      animate(art,[{opacity:0,clipPath:"inset(0 0 100% 0 round 24px)"},{opacity:1,clipPath:"inset(0 0 0% 0 round 24px)"}],180,850);
      seen.current.add(art);
    }
    const observer=new IntersectionObserver(entries => {
      entries.filter(e=>e.isIntersecting).forEach((e,i)=> {
        if(!seen.current.has(e.target)) { animate(e.target,rise,Math.min(i,4)*100); seen.current.add(e.target); }
        observer.unobserve(e.target);
      });
    },{threshold:.08});
    document.querySelectorAll(".rt-view .rt-panel,.rt-view .rt-stat,.rt-view .rt-pipeline,.rt-story-intro").forEach(el=>observer.observe(el));
    return ()=>{observer.disconnect();animations.forEach(a=>a.cancel());};
  },[view,ready,busy,active]);
  useEffect(()=>{
    if(!ready) return;
    const app=document.querySelector<HTMLElement>(".rt-app");
    const progress=document.querySelector<HTMLElement>(".rt-scroll-progress");
    const desktop=matchMedia("(min-width: 981px) and (pointer: fine)");
    let frame=0;
    const update=()=>{
      frame=0;
      const max=document.documentElement.scrollHeight-innerHeight;
      progress?.style.setProperty("--progress",String(max>0?Math.min(scrollY/max,1):0));
      app?.classList.toggle("rt-scrolled",scrollY>40);
      document.querySelectorAll<HTMLElement>("[data-parallax]").forEach(el=>{
        const b=el.getBoundingClientRect();
        const y=active&&desktop.matches?Math.max(-20,Math.min(20,(innerHeight/2-b.top-b.height/2)*.035)):0;
        el.style.setProperty("--parallax",`${y}px`);
      });
    };
    const schedule=()=>{if(!frame) frame=requestAnimationFrame(update);};
    addEventListener("scroll",schedule,{passive:true}); addEventListener("resize",schedule);
    const observer=new ResizeObserver(schedule); observer.observe(document.body); update();
    return ()=>{removeEventListener("scroll",schedule);removeEventListener("resize",schedule);observer.disconnect();cancelAnimationFrame(frame);};
  },[view,ready,active]);
  useEffect(()=>{
    if(!active || !ready || busy) return;
    const wrapper=document.querySelector<HTMLElement>(".rt-magnetic");
    const button=wrapper?.querySelector<HTMLElement>("button");
    if(!wrapper || !button) return;
    const fine=matchMedia("(hover: hover) and (pointer: fine) and (min-width: 981px)");
    const move=(e:PointerEvent)=>{
      if(!fine.matches || e.pointerType==="touch") return;
      const b=wrapper.getBoundingClientRect();
      const x=Math.max(-8,Math.min(8,(e.clientX-b.left-b.width/2)*.1));
      const y=Math.max(-8,Math.min(8,(e.clientY-b.top-b.height/2)*.15));
      button.style.translate=`${x}px ${y}px`;
    };
    const reset=()=>{button.style.translate="0px 0px";};
    wrapper.addEventListener("pointermove",move);wrapper.addEventListener("pointerleave",reset);
    return ()=>{reset();wrapper.removeEventListener("pointermove",move);wrapper.removeEventListener("pointerleave",reset);};
  },[view,ready,busy,active]);
  return active;
}

const chapters=[
  {title:"Discover the right signals.",tag:"01 / DISCOVER",body:"Start with context. Focus your watchlists, explore candidate sources, and inspect the conversations that matter to your investigation.",detail:"Target watchlists · Source qualification",view:"discovery",cta:"Explore discovery",image:"/images/cyber-portrait.jpg",alt:"White cybernetic portrait with amber detailing"},
  {title:"Connect the evidence.",tag:"02 / UNDERSTAND",body:"Separate observables from assumptions. Review source context, filter repetition, and follow the forwarding metadata that is actually available.",detail:"Noise filtering · Observable extraction · Provenance",view:"iocs",cta:"Inspect observables",image:"/images/intelligence-core.jpg",alt:"Conceptual black titanium intelligence core"},
  {title:"Make the next move clear.",tag:"03 / REVIEW",body:"Prioritize evidence for human review. Package your findings into structured intelligence and detection drafts—not unverified conclusions.",detail:"Evidence confidence · Risk scoring · STIX export",view:"review",cta:"Open review queue",image:"/images/intelligence-core.jpg",alt:"Illuminated intelligence core, conceptual artwork"},
];
export function IntelligenceStory({motion,onNavigate}:{motion:boolean;onNavigate:(view:string)=>void}) {
  const root=useRef<HTMLElement>(null);
  const [active,setActive]=useState(0);
  const [compact,setCompact]=useState(true);
  useEffect(()=>{const q=matchMedia("(max-width: 980px)");const update=()=>setCompact(q.matches);update();q.addEventListener("change",update);return()=>q.removeEventListener("change",update);},[]);
  const sequenced=motion&&!compact;
  useEffect(()=>{
    const el=root.current;if(!el) return;
    const wide=matchMedia("(min-width: 981px)");let frame=0;
    const update=()=>{frame=0;if(!motion || !wide.matches)return;
      const b=el.getBoundingClientRect();const travel=b.height-innerHeight*.78;
      setActive(Math.max(0,Math.min(2,Math.floor((-b.top+100)/Math.max(travel,1)*3))));
    };
    const scroll=()=>{if(!frame)frame=requestAnimationFrame(update);};
    addEventListener("scroll",scroll,{passive:true});addEventListener("resize",scroll);update();
    return ()=>{cancelAnimationFrame(frame);removeEventListener("scroll",scroll);removeEventListener("resize",scroll);};
  },[motion]);
  return <section ref={root} className={`rt-story ${sequenced?"":"is-static"}`} aria-label="Intelligence workflow">
    <div className="rt-story-sticky">
      <header className="rt-story-intro"><span className="rt-eyebrow">FROM SIGNAL TO PERSPECTIVE</span><h2>Intelligence. With a clear next step.</h2><p>A closer look at the workflow—not a claim of autonomous protection.</p></header>
      <div className="rt-story-stage">
        {chapters.map((chapter,i)=><article key={chapter.tag} className={`rt-story-chapter ${active===i?"is-current":""}`} aria-hidden={sequenced&&active!==i?true:undefined}>
          <div className="rt-story-art"><img src={chapter.image} alt={chapter.alt} loading="lazy" decoding="async" width="1000" height="1000"/><span>REDTRACES / {chapter.tag}</span></div>
          <div className="rt-story-copy"><span className="rt-eyebrow">{chapter.tag}</span><h3>{chapter.title}</h3><p>{chapter.body}</p><small>{chapter.detail}</small><button tabIndex={sequenced&&active!==i?-1:0} className="rt-btn rt-primary" onClick={()=>onNavigate(chapter.view)}>{chapter.cta}<span aria-hidden="true">↗</span></button></div>
        </article>)}
      </div>
      <div className="rt-story-navigation" aria-label="Workflow steps">{chapters.map((c,i)=><button key={c.tag} aria-pressed={active===i} onClick={()=>setActive(i)}><span>0{i+1}</span>{c.tag.split(" / ")[1]}<i/></button>)}</div>
    </div>
  </section>;
}
