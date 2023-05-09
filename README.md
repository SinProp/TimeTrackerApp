# Time Tracker Application

This is a time tracking application designed for measuring actual labor against estimated labor. The application was built using Python, MySQL, Flask, and is currently deployed on AWS with 10-12 Daily Users.

## Features

- **User, Shift, and Job models**: Created in MySQL, these models form the backbone of our application. They allow for structured data storage and manipulation, making it easier to manage user data, work shifts, and job details.

- **Front End Composition with Python**: Python is not only used for back-end logic but also used to design a user-friendly front-end. It provides an intuitive interface for users to interact with the application.

- **Flask Framework and MVC model**: The Flask framework is used to structure the application according to the MVC (Model-View-Controller) architecture. This design pattern is known for its ability to decouple data handling logic from user interface rendering, resulting in more organized and manageable code. It allows the modularization of functionality, making the app more scalable and maintainable.

- **User Registration Form with validations**: The application includes a user registration form with built-in validations to ensure data integrity and security. This way, we make sure that only valid and safe data is stored in our database.

- **Employee Clock-in/Clock-out Functionality**: Employees can easily clock in and out of jobs, allowing us to accurately measure actual labor against the estimated labor. This feature is crucial for better project management and resource allocation.

- **Administrative Controls**: Administrative users have the ability to adjust shifts, in case an employee forgets to punch out. They can also toggle jobs on and off the active job board, providing real-time updates on the status of various jobs.

## Getting Started

To get started with this project, follow these instructions:

1. Clone the repository: `git clone https://github.com/SinProp/TimeTrackerApp.git`
2. Install dependencies: <Provide instructions or refer to a script if you have one>
3. Run the application: <Provide instructions>

## Documentation

A Standard Operating Procedure (SOP) is available in PDF format to guide users through the application. [Access the SOP here](https://github.com/SinProp/TimeTrackerApp/blob/fe67046c3c612e4541253df95d5c4047bc875b21/Using%20The%20Island%20Time%20App%20SOP.pdf).

## Contributing

Currently, I am the maintainer and sole contributor to this project. If you'd like to contribute, please fork the repository and use a feature branch. Pull requests are warmly welcome.

## Links

- Repository: https://github.com/SinProp/TimeTrackerApp.git
- Issue tracker: https://github.com/SinProp/TimeTrackerApp/issues


