from datetime import datetime
import httpx
from pathlib import Path
import logging
from typing import TypedDict, List, Optional
import click
from pydantic import BaseModel
from dotenv import load_dotenv
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

class Document(BaseModel):
    id: str
    title: Optional[str]
    author: Optional[str]
    source_url: Optional[str]
    category: Optional[str]
    tags: Optional[dict]
    notes: Optional[str]
    summary: Optional[str]

class ReadwiseAPI:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://readwise.io/api/v3"
        self.headers = {"Authorization": f"Token {token}"}
        logger.debug(f"Readwise API token: {self.headers}")
        self.client = httpx.Client(headers=self.headers)
    
    def fetch_documents(self, updated_after: Optional[datetime] = None) -> List[Document]:
        """Fetch all documents from Readwise"""
        documents = []
        next_page_cursor = None
        
        while True:
            params = {}
            if next_page_cursor:
                params["pageCursor"] = next_page_cursor
            if updated_after:
                params["updatedAfter"] = updated_after.isoformat()
            
            logger.info(f"Fetching documents with params: {params}")
            response = self.client.get(f"{self.base_url}/list/", params=params)
            response.raise_for_status()
            data = response.json()
            
            documents.extend([Document(**doc) for doc in data["results"]])
            next_page_cursor = data.get("nextPageCursor")
            
            if not next_page_cursor:
                break
        
        return documents

def create_markdown_post(doc: Document, output_dir: Path) -> None:
    """Convert a Readwise document into a Jekyll markdown post"""
    # Create post filename with today's date
    today = datetime.now().strftime("%Y-%m-%d")
    # Create a slug from the title
    slug = doc.title.lower().replace(" ", "-")[:50]  # Limit slug length
    filename = f"{today}-{slug}.md"
    
    # Create frontmatter
    frontmatter = [
        "---",
        f"layout: post",
        f'title: "{doc.title}"',
        f"slug: {slug}",
        f"tags: [quote, readwise]",  # Add more tags as needed
        "---",
        ""
    ]
    
    # Add source attribution
    content = []
    if doc.author:
        source = f"[{doc.author}]({doc.source_url})" if doc.source_url else doc.author
        content.append(f"Quoting {source}.")
        content.append("")
    
    # Add summary if available
    if doc.summary:
        content.append(doc.summary)
        content.append("")
    
    # Add notes if available
    if doc.notes:
        content.append(doc.notes)
        content.append("")
    
    # Write to file
    output_file = output_dir / filename
    output_file.write_text("\n".join(frontmatter + content))
    logger.info(f"Created post: {output_file}")

@click.command()
@click.option("--output-dir", type=click.Path(exists=True), default=".", help="Output directory for posts")
@click.option("--updated-after", type=click.DateTime(formats=["%Y-%m-%d"]), help="Only fetch documents updated after this ISO date")
def main(output_dir: str, updated_after: Optional[datetime]):
    """Convert Readwise documents to Jekyll markdown posts"""
    # Use token from command line or fall back to environment variable
    api_token = os.getenv("READWISE_ACCESS_TOKEN")
    if not api_token:
        raise click.ClickException("No Readwise token provided. Set READWISE_TOKEN in .env file or pass --token")
    
    api = ReadwiseAPI(api_token)
    output_path = Path(output_dir)
    
    try:
        documents = api.fetch_documents(updated_after)
        logger.info(f"Found {len(documents)} documents")
        
        for doc in documents:
            try:
                create_markdown_post(doc, output_path)
            except Exception as e:
                logger.error(f"Failed to create post for document {doc.title}: {e}")
    
    except Exception as e:
        logger.error(f"Failed to fetch documents: {e}")
        raise click.ClickException(str(e))

if __name__ == "__main__":
    main() 