# Kopa Connect API

## Description
Kopa Connect API is a Python-based backend service that provides various features including security checks, chatroom creation, and user management for the Kopa Connect application.

## Features
- Authentication using JWT and OAuth2
- Blogging capabilities
- Real-time chat features using WebSockets
- Security checks on joining platoon chat
- Return chatroom ID upon joining platoon group chat
- Listing of user-joined group chats
- Platoon group chat assigning based on state code
- Chatroom creation

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/RemyAde/kopa_backend.git
    ```

2. Navigate to the project directory:
    ```sh
    cd kopa_backend
    ```

3. Create and activate a virtual environment:
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

4. Install the dependencies:
    ```sh
    pip install -r requirements.txt
    ```

## Usage

1. Run the application:
    ```sh
    uvicorn main:app --reload
    ```

2. Access the application at `http://127.0.0.1:8000`

## Contribution

1. Fork the repository.
2. Create a new branch.
3. Make your changes.
4. Submit a pull request.

## License

This project is licensed under the MIT License.

## Contact

For any inquiries, please reach out to [RemyAde](https://github.com/RemyAde).
