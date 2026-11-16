from dataclasses import dataclass, field
import requests

from uuid import uuid4, UUID

LIST_URL = "https://neocities.org/api/list"
INFO_URL = "https://neocities.org/api/info"

DOWNLOAD_FILE_URL = "https://neocities.org/api/download"

@dataclass(frozen=True)
class NeocitiesDirectory:
    filename: str
    directory_level: int

    uuid: UUID = field(default_factory=uuid4)
    parent_uuid: UUID | None = None

    def __eq__(self, other):
        return self.uuid == other.uuid

type NeocitiesDirectoryContent = NeocitiesDirectoryEntry | NeocitiesDirectory

@dataclass(frozen=True)
class NeocitiesDirectoryInfo:
    directory_entries: dict[NeocitiesDirectory, list[NeocitiesDirectoryContent]]
    directory_lookup: dict[UUID, NeocitiesDirectory]

@dataclass(frozen=True)
class NeocitiesDirectoryEntry:
    filename: str
    sha1_hash: str

    size_in_bytes: int

    uuid: UUID = field(default_factory=uuid4)

    def __eq__(self, other):
        return self.uuid == other.uuid

ROOT_DIR = NeocitiesDirectory(filename="root", directory_level=0)

def _add_or_append_directory_entry(directory_dict: dict[NeocitiesDirectory, list[NeocitiesDirectoryContent]], parent_directory: NeocitiesDirectory, directory_entry: NeocitiesDirectoryEntry | NeocitiesDirectory):
    if parent_directory in directory_dict:
        if directory_entry not in directory_dict[parent_directory]:
            directory_dict[parent_directory].append(directory_entry)
    else:
        directory_dict[parent_directory] = [directory_entry]

def _make_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}
    
def list_files(api_key: str) -> NeocitiesDirectoryInfo:
    headers = _make_headers(api_key = api_key)
    list_result = requests.get(url = LIST_URL, headers = headers)

    if list_result.ok:
        listed_files = list_result.json()["files"]
        
        listed_files_by_directory = {}
        directory_path_lookup = {ROOT_DIR.filename: ROOT_DIR}

        directory_uuid_lookup = {ROOT_DIR.uuid: ROOT_DIR}

        directories = []
        files = []

        for listed_file in listed_files:
            if listed_file["is_directory"]:
                directories.append(listed_file)
            else:
                files.append(listed_file)

        directories_by_levels = sorted(directories, key = lambda d: d["path"].count("/"), reverse = True)

        for directory in directories_by_levels:
            directory_path = directory["path"]
            all_path_directories_already_added = any(lookup_path.startswith(f"{ROOT_DIR.filename}/{directory_path}") for lookup_path in directory_path_lookup)
            
            if not all_path_directories_already_added:
                directories_so_far = [ROOT_DIR]

                directory_subpaths_str = str(directory_path)
                num_directory_subpaths = directory_subpaths_str.count("/")

                extant_lookup_last_index = -1

                while num_directory_subpaths > 0:
                    last_subpath_separator = directory_subpaths_str.rfind("/")
                    directory_subpaths_str = directory_subpaths_str[:last_subpath_separator]

                    num_directory_subpaths-=1
                    up_to_last_subpath = f"{ROOT_DIR.filename}/{directory_subpaths_str}"

                    maybe_last_subpath_lookup_result = directory_path_lookup.get(up_to_last_subpath)

                    if maybe_last_subpath_lookup_result:
                        if extant_lookup_last_index == -1:
                            extant_lookup_last_index = num_directory_subpaths

                        directories_so_far.insert(1, maybe_last_subpath_lookup_result)
                        
                directory_path_components = directory_path.split("/")
                directory_path_components_start = extant_lookup_last_index + 1 if extant_lookup_last_index > -1 else 0

                for directory_path_component_ind in range(directory_path_components_start, len(directory_path_components)):
                    most_recent_directory = directories_so_far[directory_path_component_ind]
                    directory_path_component = directory_path_components[directory_path_component_ind]

                    current_directory = NeocitiesDirectory(filename = directory_path_component, directory_level = most_recent_directory.directory_level + 1, parent_uuid = most_recent_directory.uuid)
                    _add_or_append_directory_entry(directory_dict = listed_files_by_directory, parent_directory = most_recent_directory, directory_entry = current_directory)
                    
                    directories_so_far.append(current_directory)
                    directory_names_so_far = [directory_so_far.filename for directory_so_far in directories_so_far]

                    directory_path_so_far = "/".join(directory_names_so_far)
                    directory_path_lookup[directory_path_so_far] = current_directory

                    directory_uuid_lookup[current_directory.uuid] = current_directory

        for file in files:
            file_path = file["path"]
            file_not_at_root = file_path.count("/") > 0

            if file_not_at_root:
                last_separator = file_path.rfind("/")

                path_up_to_file = f"root/{file_path[:last_separator]}"
                file_name = file_path[last_separator + 1:]

                file_entry = NeocitiesDirectoryEntry(filename = file_name, sha1_hash = file["sha1_hash"], size_in_bytes = file["size"])
                parent_directory = directory_path_lookup[path_up_to_file]

                _add_or_append_directory_entry(directory_dict = listed_files_by_directory, parent_directory = parent_directory, directory_entry = file_entry)
            else:
                file_entry = NeocitiesDirectoryEntry(filename = file_path, sha1_hash = file["sha1_hash"], size_in_bytes = file["size"])
                _add_or_append_directory_entry(directory_dict = listed_files_by_directory, parent_directory = ROOT_DIR, directory_entry = file_entry)

        return NeocitiesDirectoryInfo(directory_entries = listed_files_by_directory, directory_lookup = directory_uuid_lookup)
    else:
        print(f"{LIST_URL} {headers} request failed")
        return NeocitiesDirectoryInfo(directory_entries = {}, directory_lookup = {})

def info(api_key: str):
    headers = _make_headers(api_key = api_key)
    return requests.get(url = INFO_URL, headers = headers)

def download_file(api_key: str, path_to_file: str) -> bytes:
    headers = _make_headers(api_key = api_key)
    url = f"{DOWNLOAD_FILE_URL}?path={path_to_file}"

    response = requests.get(url = url, headers = headers)
    return response.content