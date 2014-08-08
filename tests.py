# import mock
import unittest
import uuid
import json

from werkzeug.datastructures import ImmutableMultiDict
from flask import session
from hunt import app, db

import views
import forms
import xapi
import utils
import models

import mock

app.config['DEBUG'] = True
BASIC_LOGIN = app.config['WAX_LOGIN']
BASIC_PASSWORD = app.config['WAX_PASSWORD']
WAX_SITE = app.config['WAX_SITE']


def identifier():
    return uuid.uuid4().hex


def email():
    return '{}@example.com'.format(identifier())


class HuntTestCase(unittest.TestCase):
    def registered_statement(self, hunt, email=email()):
        return {
            "actor": xapi.make_agent(email),
            "verb": {
                "id": "http://adlnet.gov/expapi/verbs/registered",
                "display": {
                    "en-US": "registered"
                }
            },
            "object": xapi.hunt_activity(hunt)
        }

    ### TESTS! ###
    def test_get_admin_id_returns_admin_id_for_existing_admin(self):
        request = mock.MagicMock()
        request.method = 'POST'
        db = mock.MagicMock()
        db.session.query.filter.first.return_value = {'admin_id': 1}
        db.session.query.filter.first.admin_id = 1
        print db.session.query.filter.first()
        form = mock.MagicMock()
        form.validate.return_value = True

        admin_id = utils.get_admin_id(request.method, db, form)

        print 'admin id: ', admin_id
        assert admin_id == 1

    def test_get_admin_id_returns_none_on_GET(self):
        request = mock.MagicMock()
        request.method = 'GET'

        db = mock.MagicMock()
        form = mock.MagicMock()

        admin_id = utils.get_admin_id(request.method, db, form)

        assert admin_id is None

    def test_get_admin_id_when_form_invalid_raises_exception(self):
        request = mock.MagicMock()
        request.method = 'POST'
        db = mock.MagicMock()

        form = mock.MagicMock()
        form.validate.return_value = False

        try:
            utils.get_admin_id(request.method, db, form)
        except Exception as e:
            assert e[0]['errors']

    def test_get_admin_id_when_no_admin_found(self):
        request = mock.MagicMock()
        request.method = 'POST'
        db = mock.MagicMock()
        db.session.query.filter.first.return_value = None

        form = mock.MagicMock()
        form.validate.return_value = True

        try:
            utils.get_admin_id(request.method, db, form)
        except Exception as e:
            assert e[0]['errors']['emails'] == 'Invalid email or password'

    # def test_login_logout(self):
    #     response = self.login(self.admin['email'], self.admin['password'])
    #     self.assertIn('You were logged in', response.data)

    #     response = self.logout()
    #     self.assertIn('Login', response.data)

    # def test_login_invalid_username(self):
    #     response = self.login(identifier(), identifier())
    #     self.assertIn('Invalid email or password', response.data)

    # def test_pages_requiring_login(self):
    #     self.login(self.admin['email'], self.admin['password'])
    #     self.create_hunt()
    #     self.logout()

    #     for route in ['/hunts', '/hunts/1', '/settings']:
    #         response = self.app.get(route, follow_redirects=True)
    #         self.assertIn('login required', response.data)

    def test_create_admin(self):
        response = self.app.get('/admins')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Admin Registration', response.data)

        admin_email = email()
        password = identifier()

        response = self.create_admin(email=admin_email, password=password)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Successfully created admin', response.data)

        self.logout()
        response = self.login(admin_email, password)
        self.assertEqual(response.status_code, 200)

    def test_create_settings(self):
        self.login(self.admin['email'], self.admin['password'])
        settings_response = self.create_settings(
            domain=identifier(), login=identifier(), password=identifier())

        self.assertEqual(settings_response.status_code, 200)
        self.assertIn(login, settings_response.data)
        self.assertIn(domain, settings_response.data)

    def test_create_and_show_hunt(self):
        self.login(self.admin['email'], self.admin['password'])
        name = identifier()
        participants = [{'email': email()} for _ in xrange(2)]
        items = [{'name': identifier()} for _ in xrange(2)]
        create_hunt_response = self.create_hunt(
            name=name, participants=participants, items=items)

        self.assertEqual(create_hunt_response.status_code, 200)

        # currently this always goes to 1 because it's a clean db
        show_hunt_response = self.app.get('/hunts/1', follow_redirects=True)
        self.assertEqual(show_hunt_response.status_code, 200)

        self.assertIn(name, show_hunt_response.data)

        for participant in participants:
            self.assertIn(participant['email'], show_hunt_response.data)

        for item in items:
            self.assertIn(item['name'], show_hunt_response.data)

    def test_delete_hunt(self):
        self.login(self.admin['email'], self.admin['password'])
        self.create_hunt()

        response = self.app.get('/hunts/1/delete', follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        response = self.app.get('/hunts/1', follow_redirects=True)
        self.assertEqual(response.status_code, 404)

    def test_get_started(self):
        self.login(self.admin['email'], self.admin['password'])
        self.create_hunt()
        self.logout()
        response = self.app.get(
            '/get_started/hunts/1', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Enter your name and email', response.data)

    def test_show_item_codes(self):
        self.login(self.admin['email'], self.admin['password'])
        item1 = {'name': identifier()}
        item2 = {'name': identifier()}
        self.create_hunt(items=[item1, item2])

        response = self.app.get('/hunts/1/qrcodes')
        self.assertEqual(response.status_code, 200)
        for item in [item1, item2]:
            self.assertIn(item['name'], response.data)

        response = self.app.get('/hunts/1/items/1/qrcode')
        self.assertEqual(response.status_code, 200)
        self.assertIn(item1['name'], response.data)

    # this also tests the show_item function/route
    def test_whitelisted_participant(self):
        with app.test_client() as c:
            self.login(self.admin['email'], self.admin['password'])
            participant_email = email()
            self.create_hunt(
                participants=[{'email': participant_email}],
                items=[{'name': identifier()}])

            self.logout()

            # necessary to access item routes
            with c.session_transaction() as sess:
                sess['email'] = participant_email
                sess['intended_url'] = '/hunts/1'

            name = identifier()
            response = self.register_participant(c, participant_email, name)
            self.assertEqual(response.status_code, 200)

            response = c.get('/hunts/1/items/1', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(name, response.data)

    def test_not_whitelisted_participant(self):
        with app.test_client() as c:
            self.login(self.admin['email'], self.admin['password'])
            self.create_hunt()
            self.logout()

            with c.session_transaction() as sess:
                sess['admin_id'] = 1

            c.get('/hunts/1/items/1', follow_redirects=True)
            response = self.register_participant(c, email(), identifier())
            self.assertIn(
                'You are not on the list of allowed participants',
                response.data
            )

    def test_index_items(self):
        self.login(self.admin['email'], self.admin['password'])
        items = [{'name': identifier()}, {'name': identifier()}]
        participants = [{'email': email()}]
        self.create_hunt(items=items, participants=participants)
        self.logout()

        self.app.get('hunts/1/items')
        response = self.register_participant(
            self.app, participants[0]['email'], identifier())
        self.assertEqual(response.status_code, 200)

        for item in items:
            self.assertIn(item['name'], response.data)

    def test_put_state_doc(self):
        with app.test_request_context('/'):
            hunt_id = 1
            session_email = email()
            params = xapi.default_params(session_email, hunt_id)

            data = {'required_ids': [1, 2]}
            setting = MockSetting(BASIC_LOGIN, BASIC_PASSWORD, WAX_SITE)

            response = xapi.put_state(json.dumps(data), params, setting)
            self.assertEqual(response.status_code, 204)

            response = xapi.get_state_response(params, setting)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), data)

    def test_post_state_doc(self):
        with app.test_request_context('/'):
            hunt_id = 1
            session_email = email()
            params = xapi.default_params(session_email, hunt_id)

            data = {'required_ids': [1, 2]}
            setting = MockSetting(BASIC_LOGIN, BASIC_PASSWORD, WAX_SITE)

            response = xapi.post_state(json.dumps(data), params, setting)
            self.assertEqual(response.status_code, 204)

    def test_send_begin_hunt_statement(self):
        with app.test_request_context('/'):
            hunt = MockHunt(1, identifier())
            statement = self.registered_statement(hunt)
            setting = MockSetting(BASIC_LOGIN, BASIC_PASSWORD, WAX_SITE)
            response = xapi.send_statement(statement, setting)
            self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()
