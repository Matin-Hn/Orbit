from locust import HttpUser, task, between

class QuicKstartUser(HttpUser):
    wait_time = between(1, 2)


    @task
    def get_channels(self):
        self.client.get("/channels")