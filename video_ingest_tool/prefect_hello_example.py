from prefect import flow, task

@task
def say_hello(name: str) -> str:
    print(f"Hello, {name}!")
    return f"Hello, {name}!"

@flow
def hello_flow():
    say_hello("World") 