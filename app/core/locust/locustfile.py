from locust import HttpUser, task, between

class QuicKstartUser(HttpUser):
    wait_time = between(1, 2)


    def on_start(self):
        response = self.client.post("/login", json={
            "username": "admin",
            "password": "Admin@321"
        })
        token = response.json()["access_token"]

        self.client.headers.update({
            "Authorization": f"Bearer {token}"
    })
    @task
    def get_users(self):
        self.client.get("/users")

    @task
    def get_channels(self):
        self.client.get("/channels")

    @task
    def get_video(self):
        self.client.get("/videos/8A3YMgrD")