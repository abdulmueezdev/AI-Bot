export const runtime = 'edge';

export async function GET() {
  try {
    const res = await fetch('https://ai-bot-tp8d.onrender.com/chat/alucard', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: 'keepalive', session_id: 'keepalive' })
    });
    const data = await res.json();
    return Response.json({ status: 'pinged', backend: data });
  } catch {
    return Response.json({ status: 'failed' }, { status: 500 });
  }
}
