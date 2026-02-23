from pathlib import Path
from git import Repo
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

def update_repo(repo_path):
    repo = Repo(repo_path)
    repo.remotes.origin.pull()

def main():
    repo_folder = Path().cwd()
    repos = [repo_path for repo_path in repo_folder.iterdir() if repo_path.is_dir()]

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(update_repo, repo) for repo in repos]

        with tqdm(total=len(futures), ncols=80, desc="Updating repositories") as pbar:
            for future in futures:
                future.result()
                pbar.update(1)

if __name__ == '__main__':
    main()