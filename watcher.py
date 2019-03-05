import mimetypes
import pickle
import os.path
import base64
import email
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from apiclient import errors

import re

# If modifying these scopes, delete the file token.pickle.
SCOPES = [
    'https://mail.google.com/',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels',
    'https://www.googleapis.com/auth/gmail.send',
]


def list_messages_with_labels(service, user_id, label_ids=[]):
    """List all Messages of the user's mailbox with label_ids applied.

    Args:
      service: Authorized Gmail API service instance.
      user_id: User's email address. The special value "me"
      can be used to indicate the authenticated user.
      label_ids: Only return Messages with these labelIds applied.

    Returns:
      List of Messages that have all required Labels applied. Note that the
      returned list contains Message IDs, you must use get with the
      appropriate id to get the details of a Message.
    """
    try:
        response = service.users().messages().list(userId=user_id,
                                                   labelIds=label_ids).execute()
        messages = []
        if 'messages' in response:
            messages.extend(response['messages'])

        while 'nextPageToken' in response:
            page_token = response['nextPageToken']
            response = service.users().messages().list(userId=user_id,
                                                       labelIds=label_ids,
                                                       pageToken=page_token).execute()
            messages.extend(response['messages'])

        return messages
    except errors.HttpError as error:
        print('An error occurred: %s' % error)


def get_message(service, user_id, msg_id):
    """Get a Message with given ID.

    Args:
      service: Authorized Gmail API service instance.
      user_id: User's email address. The special value "me"
      can be used to indicate the authenticated user.
      msg_id: The ID of the Message required.

    Returns:
      A Message.
    """
    try:
        message = service.users().messages().get(userId=user_id, id=msg_id).execute()
        return message
    except errors.HttpError as error:
        print('An error occurred: %s' % error)


def get_mime_message(service, user_id, msg_id):
    """Get a Message and use it to create a MIME Message.

    Args:
      service: Authorized Gmail API service instance.
      user_id: User's email address. The special value "me"
      can be used to indicate the authenticated user.
      msg_id: The ID of the Message required.

    Returns:
      A MIME Message, consisting of data from Message.
    """
    try:
        message = service.users().messages().get(userId=user_id, id=msg_id,
                                                 format='raw').execute()

        msg_str = base64.urlsafe_b64decode(message['raw'].encode('ASCII'))

        mime_msg = email.message_from_string(msg_str)

        return mime_msg
    except errors.HttpError as error:
        print('An error occurred: %s' % error)


def extract_email_address(message):
    emails = re.search(r"[\w\.-]+@[\w\.-]+", message)
    return emails.group()


def create_message_with_attachment(sender, to, subject, message_text, file):
    """Create a message for an email.

    Args:
      sender: Email address of the sender.
      to: Email address of the receiver.
      subject: The subject of the email message.
      message_text: The text of the email message.
      file: The path to the file to be attached.

    Returns:
      An object containing a base64url encoded email object.
    """
    message = MIMEMultipart()
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject

    msg = MIMEText(message_text, 'html')
    message.attach(msg)

    content_type, encoding = mimetypes.guess_type(file)

    if content_type is None or encoding is not None:
        content_type = 'application/octet-stream'
    main_type, sub_type = content_type.split('/', 1)
    if main_type == 'text':
        fp = open(file, 'rb')
        msg = MIMEText(fp.read(), _subtype=sub_type)
        fp.close()
    elif main_type == 'image':
        fp = open(file, 'rb')
        msg = MIMEImage(fp.read(), _subtype=sub_type)
        fp.close()
    elif main_type == 'audio':
        fp = open(file, 'rb')
        msg = MIMEAudio(fp.read(), _subtype=sub_type)
        fp.close()
    else:
        fp = open(file, 'rb')
        msg = MIMEBase(main_type, sub_type)
        msg.set_payload(fp.read())
        fp.close()
    filename = os.path.basename(file)
    msg.add_header('Content-Disposition', 'attachment', filename=filename)
    message.attach(msg)

    return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")}


def send_message(service, user_id, message):
    """Send an email message.

    Args:
      service: Authorized Gmail API service instance.
      user_id: User's email address. The special value "me"
      can be used to indicate the authenticated user.
      message: Message to be sent.

    Returns:
      Sent Message.
    """
    try:
        message = (service.users().messages().send(userId=user_id, body=message)
                   .execute())
        print('Message Id: %s' % message['id'])
        return message
    except errors.HttpError as error:
        print('An error occurred: %s' % error)
        return None


def modify_message(service, user_id, msg_id, msg_labels):
    """Modify the Labels on the given Message.

    Args:
      service: Authorized Gmail API service instance.
      user_id: User's email address. The special value "me"
      can be used to indicate the authenticated user.
      msg_id: The id of the message required.
      msg_labels: The change in labels.

    Returns:
      Modified message, containing updated labelIds, id and threadId.
    """
    try:
        message = service.users().messages().modify(userId=user_id, id=msg_id,
                                                    body=msg_labels).execute()
        return message
    except errors.HttpError as error:
        print('An error occurred: %s' % error)


def main():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """

    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('gmail', 'v1', credentials=creds)

    # Call the Gmail API
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])

    if not labels:
        print('No labels found.')
    else:
        update_label_id = ''
        for label in labels:
            if label['name'] == 'CATEGORY_UPDATES':
                update_label_id = label['id']

        for label in labels:
            if label['name'] == 'SWINGMAIL':
                msg = list_messages_with_labels(service, 'me', [label['id']])
                for m in msg:
                    mail = get_message(service, 'me', m['id'])
                    in_body_email_address = extract_email_address(mail['snippet'])
                    print(in_body_email_address)
                    if in_body_email_address:
                        with open('./template/greeting.html', 'r') as content_file:
                            content = content_file.read()
                            out_mail = create_message_with_attachment('me',
                                                                      in_body_email_address,
                                                                      'Hello from HOM',
                                                                      content,
                                                                      './template/attachments/image.jpg')
                            sent = send_message(service, 'me', out_mail)
                            if sent is not None:
                                labels_mod = {"addLabelIds": [update_label_id], "removeLabelIds": [label['id']]}
                                modify_message(service, 'me', m['id'], labels_mod)


if __name__ == '__main__':
    main()
