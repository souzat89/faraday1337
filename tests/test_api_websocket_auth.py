'''
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

'''
from builtins import str

import pytest
from faraday.server.api.modules.websocket_auth import decode_agent_websocket_token
from tests.utils.url import v2_to_v3


class TestWebsocketAuthEndpoint:
    def check_url(self, url):
        return url

    def test_not_logged_in_request_fail(self, test_client, workspace):
        res = test_client.post(self.check_url(f'/v2/ws/{workspace.name}/websocket_token/'))
        assert res.status_code == 401

    @pytest.mark.usefixtures('logged_user')
    def test_get_method_not_allowed(self, test_client, workspace):
        res = test_client.get(self.check_url(f'/v2/ws/{workspace.name}/websocket_token/'))
        assert res.status_code == 405

    @pytest.mark.usefixtures('logged_user')
    def test_succeeds(self, test_client, workspace):
        res = test_client.post(self.check_url(f'/v2/ws/{workspace.name}/websocket_token/'))
        assert res.status_code == 200

        # A token for that workspace should be generated,
        # This will break if we change the token generation
        # mechanism.
        assert res.json['token'].startswith(str(workspace.id))


class TestWebsocketAuthEndpointV3(TestWebsocketAuthEndpoint):
    def check_url(self, url):
        return v2_to_v3(url)


class TestAgentWebsocketToken:

    def check_url(self, url):
        return url

    @pytest.mark.usefixtures('session')  # I don't know why this is required
    def test_fails_without_authorization_header(self, test_client):
        res = test_client.post(
            self.check_url('/v2/agent_websocket_token/')
        )
        assert res.status_code == 401

    @pytest.mark.usefixtures('logged_user')
    def test_fails_with_logged_user(self, test_client):
        res = test_client.post(
            self.check_url('/v2/agent_websocket_token/')
        )
        assert res.status_code == 401

    @pytest.mark.usefixtures('logged_user')
    def test_fails_with_user_token(self, test_client, session):
        res = test_client.get(self.check_url('/v2/token/'))

        assert res.status_code == 200

        headers = [('Authorization', 'Token ' + res.json)]

        # clean cookies make sure test_client has no session
        test_client.cookie_jar.clear()
        res = test_client.post(
            self.check_url('/v2/agent_websocket_token/'),
            headers=headers,
        )
        assert res.status_code == 401

    @pytest.mark.usefixtures('session')
    def test_fails_with_invalid_agent_token(self, test_client):
        headers = [('Authorization', 'Agent 13123')]
        res = test_client.post(
            self.check_url('/v2/agent_websocket_token/'),
            headers=headers,
        )
        assert res.status_code == 403

    @pytest.mark.usefixtures('session')
    def test_succeeds_with_agent_token(self, test_client, agent, session):
        session.add(agent)
        session.commit()
        assert agent.token
        headers = [('Authorization', 'Agent ' + agent.token)]
        res = test_client.post(
            self.check_url('/v2/agent_websocket_token/'),
            headers=headers,
        )
        assert res.status_code == 200
        decoded_agent = decode_agent_websocket_token(res.json['token'])
        assert decoded_agent == agent


class TestAgentWebsocketTokenV3(TestAgentWebsocketToken):
    def check_url(self, url):
        return v2_to_v3(url)
