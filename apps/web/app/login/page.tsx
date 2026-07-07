'use client';
import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { API_URL } from '../../lib/api';

export default function LoginPage(){
  const router=useRouter(); const [email,setEmail]=useState('admin@fieldsight.demo'); const [password,setPassword]=useState('DemoPass123!'); const [error,setError]=useState('');
  const submit=async(e:FormEvent)=>{e.preventDefault();setError('');const r=await fetch(API_URL+'/api/v1/auth/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({email,password})});const data=await r.json();if(!r.ok){setError(typeof data.detail==='string'?data.detail:'Login failed');return;}localStorage.setItem('fieldsight.access_token',data.access_token);localStorage.setItem('fieldsight.refresh_token',data.refresh_token);localStorage.setItem('fieldsight.workspace',data.workspace_id);router.push('/');};
  return <main className="login-page"><form onSubmit={submit}><small>FIELDSIGHT EDGE · SYNTHETIC DEMO</small><h1>Enter the control center</h1><p>Use a documented demo account. No external customer data is used.</p><label>Email<input value={email} onChange={e=>setEmail(e.target.value)} type="email" required/></label><label>Password<input value={password} onChange={e=>setPassword(e.target.value)} type="password" required/></label>{error&&<p role="alert">{error}</p>}<button className="primary-button">Sign in</button></form></main>
}
