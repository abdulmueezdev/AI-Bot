import asyncio
from app.vector_store import _get_client

def main():
    client = _get_client()
    # Execute query to get all unique source_types
    # Supabase Python client doesn't have a direct distinct/group by, so let's just fetch a few records and their metadata
    response = (
        client.table("documents")
        .select("metadata")
        .eq("clone_id", "alucard")
        .limit(10)
        .execute()
    )
    for row in response.data:
        print(row.get("metadata", {}).get("source_type"))
        
    count_all = client.table("documents").select("id", count="exact").eq("clone_id", "alucard").execute()
    print("Total documents in alucard:", count_all.count)

if __name__ == "__main__":
    main()
