"use client";
import { useEffect, useState } from "react";
const API=process.env.NEXT_PUBLIC_API_URL??"http://localhost:8000/api/v1";
type Course={id:string;title:string;description:string;status:string;module_count:number;enrolled_count:number};
export default function LMSPage(){
 const [courses,setCourses]=useState<Course[]>([]); const [loading,setLoading]=useState(true); const [error,setError]=useState("");
 useEffect(()=>{fetch(API+"/lms/courses",{credentials:"include"}).then(async r=>{if(!r.ok)throw new Error("Please sign in to access the LMS.");return r.json()}).then(setCourses).catch(e=>setError(e.message)).finally(()=>setLoading(false))},[]);
 return <main className="shell"><div className="dashboard-top"><div><p className="eyebrow">LEARNING MANAGEMENT SYSTEM</p><h1>Learn, build, progress.</h1><p className="lead">Courses, structured lessons and assessments are now part of your NEXUS workspace.</p></div><a className="secondary" href="/dashboard">Control plane</a></div>
 <section className="grid dashboard-grid">{loading?<article><h2>Loading courses…</h2></article>:error?<article><h2>Sign in required</h2><p>{error}</p><a href="/login">Go to sign in</a></article>:courses.length===0?<article><h2>No courses yet</h2><p>Instructors can create the first course through the LMS API.</p></article>:courses.map(c=><article key={c.id}><p className="eyebrow">{c.status.toUpperCase()}</p><h2>{c.title}</h2><p>{c.description||"No description yet."}</p><p className="muted">{c.module_count} modules · {c.enrolled_count} learners</p></article>)}</section></main>
}