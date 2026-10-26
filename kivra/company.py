"""Company mailbox adapter for Kivra's web API."""

import logging
import os
from urllib.parse import urlsplit

from kivra.api import KivraApiClient
from kivra.letters import LetterFetcher
from kivra.models import KivraLetter
from storage.filesystem import FileSystemStoreProvider
from utils.helpers import clean_filename, format_date


GET_USER_QUERY = """
query GetUser {
  inboxes {
    key
    name
    type
  }
}
"""


CONTENT_DETAILS_QUERY = """
query ContentDetails($key: ID!) {
  content: contentV2(key: $key) {
    parts {
      name
      mimeType
      path
    }
  }
}
"""


class CompanyApiClient(KivraApiClient):
    """Select a company actor while retaining the authenticated user session."""

    def __init__(self, access_token, personal_actor_key, company_key):
        super().__init__(access_token, personal_actor_key)
        if not company_key:
            raise ValueError("Company actor key is required")
        self.company_key = company_key

    def get_headers(self):
        headers = super().get_headers()
        headers['X-Actor-Key'] = self.company_key
        headers['X-Actor-Type'] = 'company'
        return headers

    def get_content_details(self, content_key):
        response = self.graphql_query(
            'ContentDetails', CONTENT_DETAILS_QUERY, {'key': content_key}
        )
        content = (response.get('data') or {}).get('content')
        if not isinstance(content, dict) or not isinstance(content.get('parts'), list):
            raise RuntimeError(f"Company content {content_key} has no parts list")

        parts = []
        for part in content['parts']:
            if not isinstance(part, dict):
                raise RuntimeError(f"Company content {content_key} has an invalid part")
            mime_type = part.get('mimeType')
            path = part.get('path')
            if not mime_type or not path:
                raise RuntimeError(f"Company content {content_key} has a part without a type or path")
            normalized = {
                'name': part.get('name'),
                'content_type': mime_type,
                'key': path,
            }
            if mime_type in ('text/plain', 'text/html'):
                normalized['body'] = self.get_content_file(content_key, path).decode('utf-8')
            parts.append(normalized)
        return {'parts': parts}

    def get_content_file(self, content_key, file_key):
        """Fetch the path supplied by ContentDetails from the Kivra core API."""
        path = urlsplit(file_key)
        if (path.scheme or path.netloc or path.fragment or not path.path.startswith('/')
                or file_key.startswith('//') or '\\' in file_key):
            raise ValueError('Invalid company content path')
        response = self.session.get(
            f'https://app.api.kivra.com{file_key}',
            headers={'Authorization': f'token {self.access_token}'},
        )
        if response.status_code != 200:
            raise RuntimeError(f'Company content file fetch failed (HTTP {response.status_code})')
        return response.content


class CompanyLetterFetcher(LetterFetcher):
    """Mark a company letter complete only after every part is stored."""

    def _process_letter(self, letter_data, letters_stored):
        letter_key = letter_data.get('key')
        if not letter_key:
            raise RuntimeError('Company letter is missing its key')
        sender = (letter_data.get('sender') or {}).get('name') or 'unknown_sender'
        letter = KivraLetter(
            letter_key,
            format_date(letter_data.get('receivedAt')),
            sender,
        )
        metadata = letter.get_metadata()
        if self.document_store.exists(metadata):
            print(f'Skipping letter {letter_key} - already fetched')
            return letters_stored

        print(f'\nProcessing letter: {letter_key}')
        content = self.api_client.get_content_details(letter_key)
        parts = content.get('parts')
        if not parts:
            raise RuntimeError(f'Company letter {letter_key} has no parts')
        stored = self._process_letter_parts(letter, content)
        if stored != len(parts):
            raise RuntimeError(f'Company letter {letter_key}: stored {stored} of {len(parts)} parts')
        if not self.document_store.report_metadata(
            {**letter_data, 'content': content}, metadata
        ):
            raise RuntimeError(f'Could not store metadata for company letter {letter_key}')
        print(f'Saved metadata for letter {letter_key}')
        return letters_stored + 1


def fetch_company_mailboxes(personal_client, document_store, personal_folder, max_count=None):
    """Discover and fetch every company inbox in the authenticated user session."""
    response = personal_client.graphql_query('GetUser', GET_USER_QUERY, {})
    inboxes = (response.get('data') or {}).get('inboxes')
    if not isinstance(inboxes, list):
        raise RuntimeError('GetUser did not return an inbox list')

    totals = {'letters_total': 0, 'letters_fetched': 0, 'letters_stored': 0}
    errors = []
    filesystem = isinstance(document_store, FileSystemStoreProvider)
    folder_names = {os.path.normcase(personal_folder)} if filesystem else set()

    for inbox in inboxes:
        if not isinstance(inbox, dict):
            errors.append('GetUser returned an invalid inbox')
            logging.error(errors[-1])
            continue
        if inbox.get('type') == 'user':
            continue

        name = inbox.get('name')
        try:
            if not isinstance(name, str) or not name.strip():
                raise ValueError('company mailbox is missing its name')
            company_key = inbox.get('key')
            if not isinstance(company_key, str) or not company_key:
                raise ValueError('company mailbox is missing its actor key')
            if filesystem:
                folder = clean_filename(name, replace='').strip(' .')
                if not folder:
                    raise ValueError('company mailbox has no usable folder name')
                normalized = os.path.normcase(folder)
                if normalized in folder_names:
                    raise ValueError(f'company mailbox folder {folder!r} collides with another mailbox')
                folder_names.add(normalized)
                company_store = FileSystemStoreProvider(
                    os.path.join(os.path.dirname(document_store.base_dir), folder),
                    dry_run=document_store.dry_run,
                )
            else:
                company_store = document_store

            client = CompanyApiClient(
                personal_client.access_token, personal_client.actor_key, company_key
            )
            print(f'\nFetching company mailbox: {name}')
            mailbox_stats = CompanyLetterFetcher(client, company_store).fetch_letters(
                max_count=max_count
            )
            for key in totals:
                totals[key] += mailbox_stats[key]
        except Exception as exc:
            errors.append(name)
            logging.error('Company mailbox %s failed: %s', name, exc)

    return totals, errors
