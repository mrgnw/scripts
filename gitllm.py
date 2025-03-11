# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests", 
#     "tqdm",
#     "argparse",
#     "aiohttp",
#     "asyncio",
#     "rich"
# ]
# ///
import os
import requests
import json
import argparse
import asyncio
import aiohttp
from pathlib import Path
import sys
from fnmatch import fnmatch
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.tree import Tree
from rich import print as rprint
from tqdm.asyncio import tqdm as async_tqdm

# Configuration
DEFAULT_BRANCH = 'main'
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')  # Set your GitHub token in env variables
OUTPUT_FILE = 'repo_files.md'  # Updated default file name
HEADERS = (
    {'Authorization': f'bearer {GITHUB_TOKEN}', 'Content-Type': 'application/json'} if GITHUB_TOKEN else {}
)

# Initialize rich console
console = Console()

# File patterns to fetch
INCLUDE_PATTERNS = [
    'package.json',
    '**/*.config.js',
    '**/*.config.ts',
    'src/routes/**/*.svelte',
    'src/routes/**/*.js',
    'src/routes/**/*.ts',
    # Adding more general patterns for all JavaScript, TypeScript, and Svelte files
    '**/*.js',
    '**/*.ts',
    '**/*.svelte',
    '**/*.json'
]


def graphql_query(query, variables=None):
    url = 'https://api.github.com/graphql'
    payload = {'query': query, 'variables': variables or {}}
    response = requests.post(url, headers=HEADERS, json=payload)
    response.raise_for_status()
    return response.json()


async def async_graphql_query(session, query, variables=None):
    url = 'https://api.github.com/graphql'
    payload = {'query': query, 'variables': variables or {}}
    async with session.post(url, json=payload, headers=HEADERS) as response:
        response.raise_for_status()
        return await response.json()


def get_all_files(repo, branch='main'):
    """Get all files in the repository using a single GraphQL query with Git tree."""
    owner, name = repo.split('/')
    
    # First, try to get the default branch
    with console.status(f"[bold green]Checking repository {repo}...", spinner="dots"):
        query = """
        query($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) {
            defaultBranchRef {
              name
            }
          }
        }
        """
        
        data = graphql_query(query, {'owner': owner, 'name': name})
        
        if 'data' not in data or data['data'] is None or not data['data'].get('repository'):
            raise ValueError(f"Error fetching repository data. API response: {data}")
        
        repository = data['data'].get('repository')
        
        # Use default branch if main is not available
        if branch == 'main' and repository.get('defaultBranchRef'):
            default_branch = repository['defaultBranchRef']['name']
            if default_branch != branch:
                console.print(f"[yellow]Using default branch:[/] [bold cyan]{default_branch}[/]")
                branch = default_branch
    
    # Use Git Trees API directly - more reliable for full repository listing
    rest_api_url = f"https://api.github.com/repos/{owner}/{name}/git/trees/{branch}?recursive=1"
    console.print(f"[bold]Fetching file list from:[/] [blue]{rest_api_url}[/]")
    
    with console.status("[bold green]Downloading repository structure...", spinner="dots"):
        response = requests.get(rest_api_url, headers=HEADERS)
        response.raise_for_status()
        
        all_files = []
        tree_data = response.json()
        
        if tree_data.get('truncated', False):
            console.print("[bold yellow]Warning:[/] Repository tree is too large and was truncated. Some files may be missing.")
        
        # Print total number of files found
        total_files = len(tree_data.get('tree', []))
        console.print(f"Total files in repository: [bold cyan]{total_files}[/]")
        
        # Process all blob entries (files)
        for item in tree_data.get('tree', []):
            if item['type'] == 'blob':  # Only include files, not directories
                all_files.append({
                    'path': item['path'],
                    'type': item['type']
                })
        
        console.print(f"Total blob entries: [bold cyan]{len(all_files)}[/]")
    
    # Filter files based on patterns
    matching_files = []
    for file in all_files:
        for pattern in INCLUDE_PATTERNS:
            if fnmatch(file['path'], pattern):
                matching_files.append(file)
                break  # No need to check other patterns
    
    # Display matching files as a tree
    file_tree = Tree("[bold]Matching files found:[/]")
    
    # Group files by directory for better visualization
    file_paths = [file['path'] for file in matching_files]
    file_paths.sort()
    
    # Build directory tree
    path_dict = {}
    for path in file_paths:
        parts = path.split('/')
        current_dict = path_dict
        for i, part in enumerate(parts):
            if i == len(parts) - 1:  # If it's the last part (file)
                if 'files' not in current_dict:
                    current_dict['files'] = []
                current_dict['files'].append(part)
            else:  # If it's a directory
                if part not in current_dict:
                    current_dict[part] = {}
                current_dict = current_dict[part]
    
    # Function to build tree display
    def build_tree(tree_node, path_dict, is_root=False):
        # Add directories first
        for key, value in sorted(path_dict.items()):
            if key != 'files':
                dir_node = tree_node.add(f"[bold blue]{key}/[/]")
                build_tree(dir_node, value)
        
        # Then add files
        if 'files' in path_dict:
            for file in sorted(path_dict['files']):
                ext = file.split('.')[-1] if '.' in file else ''
                if ext in ['js', 'ts']:
                    tree_node.add(f"[yellow]{file}[/]")
                elif ext == 'json':
                    tree_node.add(f"[green]{file}[/]")
                elif ext == 'svelte':
                    tree_node.add(f"[orange1]{file}[/]")
                else:
                    tree_node.add(f"[white]{file}[/]")
    
    # Build and display the tree
    build_tree(file_tree, path_dict, True)
    console.print(file_tree)
    
    console.print(f"\nFound [bold green]{len(matching_files)}[/] matching files. Fetching content...")
    
    # Generate a markdown representation of the tree for the output file
    # Use GitHub-flavored markdown tree format
    md_tree_content = []
    
    def build_md_tree(path_dict, prefix=""):
        items = sorted([(k, v) for k, v in path_dict.items() if k != "files"])
        file_items = path_dict.get("files", [])
        
        # Process all items except the last one with ├── prefix
        for i, (key, value) in enumerate(items[:-1] if items else []):
            md_tree_content.append(f"{prefix}├── 📁 {key}/")
            new_prefix = f"{prefix}│   "
            build_md_tree(value, new_prefix)
        
        # Process the last directory item with └── prefix
        if items:
            key, value = items[-1]
            md_tree_content.append(f"{prefix}└── 📁 {key}/")
            new_prefix = f"{prefix}    "
            build_md_tree(value, new_prefix)
        
        # Process files with appropriate prefixes
        sorted_files = sorted(file_items)
        for i, file in enumerate(sorted_files):
            ext = file.split('.')[-1] if '.' in file else ''
            icon = "📄"
            if ext in ['js', 'ts']:
                icon = "🟨"
            elif ext == 'json':
                icon = "🔧"
            elif ext == 'svelte':
                icon = "🔥"
            elif ext in ['md', 'markdown']:
                icon = "📝"
                
            # Use different prefix for last item
            if i == len(sorted_files) - 1:
                md_tree_content.append(f"{prefix}└── {icon} {file}")
            else:
                md_tree_content.append(f"{prefix}├── {icon} {file}")
    
    build_md_tree(path_dict)
    md_tree = "\n".join(md_tree_content)
    
    return matching_files, md_tree


async def fetch_content_async(repo, files, branch):
    """Fetch file contents asynchronously with individual progress bars for each file."""
    owner, name = repo.split('/')
    
    # Set up a rich progress display with multiple tasks
    results = []
    
    # Create multi-progress display
    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("•"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        # Create a task for each file
        tasks = {}
        for i, file in enumerate(files):
            # Truncate file name if it's too long for display
            display_name = file['path']
            if len(display_name) > 40:
                display_name = "..." + display_name[-37:]
                
            tasks[file['path']] = progress.add_task(
                f"[cyan]{display_name}[/]", 
                total=1.0,
                completed=0.0
            )
        
        # Process files with proper progress tracking
        async with aiohttp.ClientSession() as session:
            # Process in batches to avoid hitting rate limits
            batch_size = 5  # Adjust based on API rate limits
            for i in range(0, len(files), batch_size):
                batch = files[i:i+batch_size]
                
                # Create tasks for each file in the batch
                batch_tasks = []
                for file in batch:
                    task = asyncio.create_task(
                        fetch_file_with_progress(
                            session, repo, file['path'], branch, 
                            progress, tasks[file['path']]
                        )
                    )
                    batch_tasks.append(task)
                
                # Wait for this batch to complete
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # Process results from this batch
                for j, result in enumerate(batch_results):
                    file_path = batch[j]['path']
                    if isinstance(result, Exception):
                        console.print(f"[red]Error fetching {file_path}: {result}[/]")
                        # Ensure progress bar is completed even on error
                        progress.update(tasks[file_path], completed=1.0)
                    else:
                        results.append({
                            'path': file_path,
                            'content': result
                        })
    
    return results


async def fetch_file_with_progress(session, repo, path, branch, progress, task_id):
    """Fetch a single file with progress tracking."""
    # First update to show we're starting
    progress.update(task_id, completed=0.1)
    
    try:
        # Fetch the file content
        content = await fetch_file_content_async(session, repo, path, branch)
        # Mark as complete
        progress.update(task_id, completed=1.0)
        return content
    except Exception as e:
        progress.update(task_id, completed=1.0)
        raise e


async def fetch_file_content_async(session, repo, path, branch='main'):
    """Fetch content of a specific file asynchronously."""
    query = """
    query($owner: String!, $name: String!, $expression: String!) {
      repository(owner: $owner, name: $name) {
        object(expression: $expression) {
          ... on Blob {
            text
          }
        }
      }
    }
    """
    owner, name = repo.split('/')
    expression = f"{branch}:{path}"
    data = await async_graphql_query(session, query, {'owner': owner, 'name': name, 'expression': expression})
    
    # Check if file exists
    if ('data' not in data or 
        not data['data'].get('repository') or 
        not data['data']['repository'].get('object')):
        raise ValueError(f"File '{path}' not found")
    
    return data['data']['repository']['object'].get('text', '')


def parse_args():
    parser = argparse.ArgumentParser(description='Generate a structure document from GitHub repository files')
    parser.add_argument('repo', nargs='?', help='GitHub repository in format owner/repo')
    parser.add_argument('output', nargs='?', default=OUTPUT_FILE, help='Output markdown file path')
    parser.add_argument('--repo', dest='repo_option', help='GitHub repository in format owner/repo')
    parser.add_argument('--branch', default='main', help='Repository branch (default: main)')
    parser.add_argument('--patterns', nargs='+', help='File patterns to include')
    parser.add_argument('--all', action='store_true', help='Include all js/ts/svelte/json files')
    parser.add_argument('--preview', action='store_true', help='Preview the markdown in terminal')
    args = parser.parse_args()
    
    # Use the positional argument if provided, otherwise use the named argument
    if not args.repo and not args.repo_option:
        parser.error("Repository name is required. Provide it as a positional argument or with --repo")
    
    # Positional argument takes precedence
    final_args = args
    final_args.repo = args.repo or args.repo_option
    delattr(final_args, 'repo_option')
    
    return final_args


async def async_main():
    args = parse_args()
    
    if not args.repo or '/' not in args.repo:
        console.print("[bold red]Error:[/] Please provide a valid repository in the format 'owner/repo'")
        sys.exit(1)
    
    # Show title
    console.print(Panel.fit(
        f"[bold cyan]GitHub Repository Explorer[/]\n[green]{args.repo}[/] (branch: [yellow]{args.branch}[/])",
        border_style="cyan"
    ))
    
    global INCLUDE_PATTERNS
    if args.patterns:
        INCLUDE_PATTERNS = args.patterns
    elif args.all:
        # Use simplified patterns if --all flag is provided
        INCLUDE_PATTERNS = [
            '**/*.js',
            '**/*.ts',
            '**/*.svelte',
            '**/*.json'
        ]
        
    output_file = args.output
    
    try:
        console.print(f"[bold]Fetching repository structure for [green]{args.repo}[/] (branch: [yellow]{args.branch}[/])...")
        matching_files, md_tree = get_all_files(args.repo, args.branch)
        
        if not matching_files:
            console.print("[yellow]No files matched the specified patterns.[/]")
            return
        
        # No need to repeat the file count here - removed redundant message
        
        # Process files in sorted order for consistent output
        matching_files.sort(key=lambda f: f['path'])
        
        # Fetch file contents asynchronously
        file_contents = await fetch_content_async(args.repo, matching_files, args.branch)
        
        # Check if we actually got content for all files - simplified message
        console.print(f"Successfully fetched [bold green]{len(file_contents)}/{len(matching_files)}[/] files")
        
        # Extract repository name for the header
        repo_name = args.repo.split('/')[1]
        
        # Generate markdown with tree structure at the top - more GitHub-friendly format
        md_content = f'# {repo_name} Project Structure\n\n'
        md_content += "## File Tree\n\n"
        md_content += md_tree
        md_content += "\n\n## File Contents\n\n"
        
        for file_data in file_contents:
            file_path = file_data['path']
            content = file_data['content']
            # Add language-specific syntax highlighting
            extension = file_path.split('.')[-1] if '.' in file_path else ''
            md_content += f"### {file_path}\n\n```{extension}\n{content}\n```\n\n"
        
        Path(args.output).write_text(md_content, encoding='utf-8')
        console.print(f"[bold green]Generated:[/] {args.output}")
        
        if args.preview:
            console.print("\n[bold]Preview of the generated document:[/]")
            md = Markdown(md_content[:1000] + "...\n\n(Output truncated for preview)")
            console.print(md)
    
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        sys.exit(1)


def main():
    asyncio.run(async_main())


if __name__ == '__main__':
    main()
