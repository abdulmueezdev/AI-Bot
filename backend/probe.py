from app.embedder import embed_texts
import asyncio

async def probe():
    # Try embedding 5 texts — if this works, we have at least 5 requests available
    texts = [
        'kafka father hermann',
        'prague insurance office',
        'tuberculosis writing night',
        'felice milena letters',
        'metamorphosis gregor samsa'
    ]
    try:
        results = await embed_texts(texts, clone_id='probe')
        print(f'Success: {len(results)} embeddings returned')
    except Exception as e:
        print(f'Failed at probe: {e}')

asyncio.run(probe())
