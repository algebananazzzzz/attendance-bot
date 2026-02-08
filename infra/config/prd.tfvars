project_code = "attendancebot"
env          = "prd"
vpc_subnet_name_labels = [
  "$env-app-subnet-private-1b",
  "$env-app-subnet-private-1a",
]
vpc_security_group_name_labels = [
  "com-app-sg-allownat",
]
