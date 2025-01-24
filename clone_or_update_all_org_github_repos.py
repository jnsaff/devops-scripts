# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests",
#     "aiohttp",
# ]
# ///

#!/usr/bin/env python3
import os
import sys
import requests
import subprocess
from pathlib import Path
import argparse
import logging
import random
import asyncio
import aiohttp
from asyncio import Semaphore

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GitHubRepoSync:
    def __init__(self, token, org_name, base_path=None, max_concurrent=10):
        """
        Initialize the GitHub repository synchronization tool.
        
        Args:
            token (str): GitHub personal access token
            org_name (str): Name of the GitHub organization
            base_path (str, optional): Base path for cloning repositories
            max_concurrent (int): Maximum number of concurrent repository operations
        """
        self.token = token
        self.org_name = org_name
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.api_base = 'https://api.github.com'
        self.semaphore = Semaphore(max_concurrent)
        self.errors = []  # Add error collection list

    def get_repositories(self):
        """Fetch all repositories for the organization."""
        repos = []
        page = 1
        
        while True:
            url = f'{self.api_base}/orgs/{self.org_name}/repos'
            params = {'page': page, 'per_page': 100}
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            page_repos = response.json()
            if not page_repos:
                break
                
            repos.extend(page_repos)
            page += 1
            
        return repos

    async def sync_repository(self, repo):
        """
        Sync a single repository - either clone it or pull latest changes.
        
        Args:
            repo (dict): Repository information from GitHub API
        """
        async with self.semaphore:
            repo_name = repo['name']
            repo_path = self.base_path / repo_name
            ssh_url = repo['ssh_url']

            if repo_path.exists():
                logger.info(f"Pulling latest changes for {repo_name}")
                try:
                    process = await asyncio.create_subprocess_exec(
                        'git', 'pull',
                        cwd=repo_path,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    if process.returncode == 0:
                        logger.info(f"Successfully updated {repo_name}")
                    else:
                        error_msg = f"Failed to pull {repo_name}: {stderr.decode()}"
                        logger.error(error_msg)
                        self.errors.append(error_msg)
                except Exception as e:
                    error_msg = f"Failed to pull {repo_name}: {str(e)}"
                    logger.error(error_msg)
                    self.errors.append(error_msg)
            else:
                logger.info(f"Cloning {repo_name}")
                try:
                    process = await asyncio.create_subprocess_exec(
                        'git', 'clone', ssh_url,
                        cwd=self.base_path,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    if process.returncode == 0:
                        logger.info(f"Successfully cloned {repo_name}")
                    else:
                        error_msg = f"Failed to clone {repo_name}: {stderr.decode()}"
                        logger.error(error_msg)
                        self.errors.append(error_msg)
                except Exception as e:
                    error_msg = f"Failed to clone {repo_name}: {str(e)}"
                    logger.error(error_msg)
                    self.errors.append(error_msg)

    async def sync_all_repositories(self):
        """Synchronize all repositories in the organization."""
        try:
            repos = self.get_repositories()
            logger.info(f"Found {len(repos)} repositories in {self.org_name}")
            
            # Randomize the order of repositories
            random.shuffle(repos)
            
            tasks = [self.sync_repository(repo) for repo in repos]
            await asyncio.gather(*tasks)
            
            if self.errors:
                logger.error("\nSummary of all errors:")
                for error in self.errors:
                    logger.error(error)
            
            logger.info("Repository synchronization completed")
        except Exception as e:
            logger.error(f"Failed to fetch repositories: {e}")
            sys.exit(1)

async def async_main():
    parser = argparse.ArgumentParser(description='Sync GitHub organization repositories')
    parser.add_argument('--token', required=True, help='GitHub personal access token')
    parser.add_argument('--org', required=True, help='GitHub organization name')
    parser.add_argument('--path', help='Base path for repositories', default=None)
    parser.add_argument('--concurrent', type=int, default=10, help='Maximum number of concurrent operations')
    
    args = parser.parse_args()
    
    syncer = GitHubRepoSync(args.token, args.org, args.path, args.concurrent)
    await syncer.sync_all_repositories()

def main():
    asyncio.run(async_main())

if __name__ == '__main__':
    main()