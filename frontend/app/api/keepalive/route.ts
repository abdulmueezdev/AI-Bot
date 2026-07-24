export const runtime = 'edge';

export async function GET() {
  try {
    const res = await fetch('https://ai-bot-tp8d.onrender.com/health', {
      method: 'GET',
    });
    const data = await res.json();
    return Response.json({ status: 'pinged', backend: data });
  } catch {
    return Response.json({ status: 'failed' }, { status: 500 });
  }
}
