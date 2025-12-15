from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from json import dumps
from datetime import datetime, timezone
from random import choices
from string import ascii_letters, ascii_uppercase, digits
from os import path

import pickle
import argparse

# If modifying these scopes, delete the file token.json.
SCOPES = 'https://www.googleapis.com/auth/tasks'
GOOGLE_APPLICATION_CREDENTIALS = '/home/user/nikita/Projects/gtasks-cli/gtasks/credentials.json'

class TaskHelper(object):
    """Allows easy interfacing with google-tasks api
    Attributes:
        self.service (api service) Service specific to this instance
        self.tasklists (list of Jsons) Stores current tasklists
        self.tasklist_ids (map String -> String) Maps tasklist names to their ids
    """
    def __init__(self, token_path=""):
        """Returns Resource object for authorized user
        Args:
            token_path (str): path to token.json. Default: ""
        """
        # Get credentials
        creds = None
        if path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            creds = self._gen_token(creds)
        self.service = build('tasks', 'v1', credentials=creds)
        self.update_tasklists()
        self.check_rep()


    def _gen_token(self, creds):
        """Lets user login and generates token"""
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
        return creds


    def check_rep(self):
        assert self.service is not None, "Uninitialized service"
        assert self.tasklists_json is not None, "Uninitialized store of tasklists"


    def update_tasklists(self):
        self.tasklists_json = self.service.tasklists().list().execute()
        self.tasklist_ids = {}
        tasklists = self.tasklists_json.get('items', [])
        for t_list in tasklists:
            # Potential ToDo, although kinda silly
            if t_list['title'] in self.tasklist_ids:
                raise ValueError("Can't handle two identically named tasklists.")
            self.tasklist_ids[t_list['title']] = t_list['id']


    def print_tasks(self):
        """Prints hierarchy of tasklists/tasks/subtasks"""
        self.check_rep()
        self.update_tasklists()
        task_lists = self.tasklists_json.get('items', [])
        tasks_request = self.service.tasks()

        for t_list in task_lists:
            print('{0}'.format(t_list['title']))
            curr_tasks_json = tasks_request.list(tasklist=t_list['id'], showCompleted=False)
            curr_tasks = curr_tasks_json.execute().get('items', [])
            padding = '  '
            # ToDo: Currently counts blank tasks as tasks. Check for empty titles
            if len(curr_tasks) == 0:
                print('{}(empty)'.format(padding))
            for task in curr_tasks:
                block = 25
                if 'parent' in task:
                    padding = '    '
                    block -= 2
                print('{0}{1:<{2}}'.format(padding, task['title'], block))
        self.check_rep()


    def add_task(self, tasklist_title, text, parent=None):
        """Adds given task to given tasklist
        Args:
            tasklist (str): name of tasklist under which to insert task
            text (str): text of the task
            parent (str): id of parent task
        """
        self.check_rep()
        # Generating task json
        # Currently not worried about security for etag or id_suffix. Potential ToDo
        local_time = datetime.now(timezone.utc).astimezone()
        etag = ''.join(choices(ascii_uppercase + digits, k=6))
        id_suffix = ''.join(choices(ascii_letters, k=5))

        new_task = {'status': 'needsAction',
                    'kind': 'tasks#task',
                    'updated': local_time.isoformat(),
                    'links': [],
                    'title': text,
                    'deleted': False,
                    'etag': etag,
                    'hidden': False,
                    'id': text + id_suffix}
        if parent is not None:
            new_task['parent'] = parent
        new_task_json = dumps(new_task)

        tasklist_id = self.tasklist_ids[tasklist_title]
        print("Adding task to: {}".format(tasklist_title))
        tasks_request = self.service.tasks()
        request = tasks_request.insert(tasklist=tasklist_id, body=new_task_json)
        request.execute() 
        self.check_rep()


def handle_args(task_helper, args):
    """Handles given args. Assumes args are valid
    Args:
        task_helper (TaskHelper): Passed TaskHelper
        args (Namespace): Passed arguments
    """
    tlist, task, parent = args.tlist, args.task, args.parent
    show = args.show

    if show:
        task_helper.print_tasks()
    if task:
        task_helper.add_task(tlist, task, parent)

def validate_args(parser, args):
    if args.tlist and args.task is None:
        parser.error('--list (-l) requires --task (-t)')
    if args.task and args.tlist is None:
        parser.error('--task (-t) requres --list (-l)')
    if args.parent and args.task is None:
        parser.error('--parent (-p) requres --task (-t)')


def main():
    parser = argparse.ArgumentParser(description='Parse gtasks_cli args')
    # ToDo Allow script to remember previously used tasklist and use as default
    parser.add_argument('-l', '--list', dest='tlist', help='Parent list for added task')
    parser.add_argument('-t', '--task', dest='task', help='Add a task')
    parser.add_argument('-p', '--parent', dest='parent', help='Add a task under a parent task')
    parser.add_argument('-s', '--show', dest='show', action='store_true', help='Print current existing task list')

    args = parser.parse_args()
    validate_args(parser, args)

    token_path = ""
    task_helper = TaskHelper(token_path)

    handle_args(task_helper, args)


if __name__ == '__main__':
    main()
