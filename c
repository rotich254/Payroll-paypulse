<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>PayPulse - Modern Payroll System</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700&display=swap">
  <script type="module" crossorigin src="{% static 'css/script.js'%}"></script>
  <link rel="stylesheet" crossorigin href="{% static 'css/style.css' %}">
</head>
<body>
  <div class="d-flex" id="wrapper">
    <!-- Sidebar -->
    {% include 'sidebar.html'%}
    
    <!-- Page Content -->
    <div id="page-content-wrapper">
      <!-- ... existing navbar code ... -->

      <div class="container-fluid px-4">
        <!-- ... existing cards code ... -->

        <!-- ... existing tables code ... -->

        <!-- Charts Section -->
        <div class="row my-5">
          <div class="col-md-7">
            <div class="bg-white rounded shadow p-4">
              <h3 class="fs-4 mb-3">Payroll Distribution</h3>
              <canvas id="payrollChart" width="400" height="250"></canvas>
            </div>
          </div>
          <div class="col-md-5">
            <div class="bg-white rounded shadow p-4">
              <h3 class="fs-4 mb-3">Department Breakdown</h3>
            </div>
          </div>
        </div>

        <!-- Employee Quick Actions Section -->
        <div class="row my-5">
          <div class="col-12">
            <div class="bg-white rounded shadow p-4">
              <!-- ... existing quick actions code ... -->
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Add your JavaScript includes here -->
</body>
</html>