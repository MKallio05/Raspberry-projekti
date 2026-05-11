import time
from grove.button import Button
from grove.factory import Factory
import requests
from grove.gpio import GPIO

# ================= SETTINGS =================
SERVER             = "http://172.17.130.130:5000"
ULTRASONIC_PIN     = 18
DISTANCE_THRESHOLD = 10  # cm

usleep = lambda x: time.sleep(x / 1_000_000)

_TIMEOUT1 = 1000
_TIMEOUT2 = 10000


# ================= LED + BUTTON =================
class GroveLedButton:
    def __init__(self, pin, action="bet_up"):
        # action: "bet_up" or "bet_down"
        self.__action = action
        self.__led = Factory.getOneLed("GPIO-HIGH", pin)
        self.__btn = Factory.getButton("GPIO-LOW", pin + 1)
        self.__on_event = None
        self.__btn.on_event(self, GroveLedButton.__handle_event)

    @property
    def on_event(self):
        return self.__on_event

    @on_event.setter
    def on_event(self, callback):
        if not callable(callback):
            return
        self.__on_event = callback

    def __handle_event(self, evt):
        if callable(self.__on_event):
            self.__on_event(evt['index'], evt['code'], evt['time'])
            return

        self.__led.brightness = self.__led.MAX_BRIGHT
        event = evt['code']
        if event & Button.EV_SINGLE_CLICK:
            self.__led.light(True)
            try:
                if self.__action == "bet_up":
                    print("bet up")
                    requests.get(f"{SERVER}/pi/bet_up", timeout=5)
                elif self.__action == "bet_down":
                    print("bet down")
                    requests.get(f"{SERVER}/pi/bet_down", timeout=5)
            except requests.exceptions.ConnectionError:
                print("Could not reach server")

    def trigger(self):
        self.__led.light(True)
        print("Ultrasonic triggered, spinning...")
        try:
            requests.post(f"{SERVER}/pi/spin", timeout=5)
        except requests.exceptions.ConnectionError:
            print("Could not reach server")


# ================= ULTRASONIC SENSOR =================
class GroveUltrasonicRanger:
    def __init__(self, pin=ULTRASONIC_PIN):
        self.dio = GPIO(pin)
        self.was_over = False

    def _get_distance(self):
        self.dio.dir(GPIO.OUT)
        self.dio.write(0)
        usleep(2)
        self.dio.write(1)
        usleep(10)
        self.dio.write(0)

        self.dio.dir(GPIO.IN)

        count = 0
        while count < _TIMEOUT1 and not self.dio.read():
            count += 1
        if count >= _TIMEOUT1:
            return None

        t1 = time.time()
        count = 0
        while count < _TIMEOUT2 and self.dio.read():
            count += 1
        if count >= _TIMEOUT2:
            return None

        t2 = time.time()
        return ((t2 - t1) * 1_000_000 / 29 / 2)

    def check_distance(self, trigger_callback):
        dist = self._get_distance()
        if dist is not None and dist > DISTANCE_THRESHOLD:
            if not self.was_over:
                print(f"Ultrasonic triggered! Distance: {dist:.1f} cm")
                trigger_callback()
            self.was_over = True
        else:
            self.was_over = False


# ================= MAIN =================
def main():
    ledbtn1 = GroveLedButton(5,  action="bet_up")    # button 1 → bet up
    ledbtn2 = GroveLedButton(22, action="bet_down")  # button 2 → bet down

    sonar = GroveUltrasonicRanger()

    print("Starting main loop...")

    while True:
        sonar.check_distance(ledbtn1.trigger)
        time.sleep(0.1)

if __name__ == '__main__':
    main()