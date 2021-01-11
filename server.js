require("dotenv-safe").config();
const express = require("express");
const bodyParser = require("body-parser");
const morgan = require("morgan");
const compression = require("compression");
const helmet = require("helmet");
const path = require("path");
const fileUpload = require("express-fileupload");
const { v4: uuid } = require("uuid");
const { exec, spawn } = require("child_process");
const sharp = require("sharp");

const app = express();
const http = require("http").Server(app);
const io = require("socket.io")(http);

if (process.env.NODE_ENV === "development") {
  app.use(morgan("dev"));
}

if (process.env.USE_REDIS === "true") {
  const getExpeditiousCache = require("express-expeditious");
  const cache = getExpeditiousCache({
    namespace: "expresscache",
    defaultTtl: "1 minute",
    engine: require("expeditious-engine-redis")({
      host: process.env.REDIS_HOST,
      port: process.env.REDIS_PORT,
    }),
  });
  app.use(cache);
}

app.use(
  bodyParser.json({
    limit: "20mb",
  })
);

app.use(
  bodyParser.urlencoded({
    limit: "20mb",
    extended: true,
  })
);

app.use(
  fileUpload({
    limits: { fileSize: 50 * 1024 * 1024 },
    safeFileNames: true,
  })
);

// app.use(compression());
// app.use(helmet());

app.use(express.static("public"));
app.set("views", path.join(__dirname, "views"));
app.engine("html", require("ejs").renderFile);
app.set("view engine", "html");

function linedraw(socketId, nama_file) {
  const ls = spawn(
    `python3 ./processor/linedraw/linedraw.py`,
    [`-i`, `./input/${nama_file}`, `-o`, `./public/output/${nama_file}.svg`],
    { cwd: __dirname, shell: true }
  );

  ls.stdout.on("data", (data) => {
    io.to(socketId).emit("event", {
      error: false,
      data: `linedraw: \nstdout: ${data}\n`,
    });
    console.log(`linedraw: stdout: ${data}`);
  });

  ls.stderr.on("data", (data) => {
    io.to(socketId).emit("event", {
      error: true,
      data: `linedraw: \nstderr: ${data}\n`,
    });
    console.log(`linedraw: stderr: ${data}`);
  });

  ls.on("error", (error) => {
    io.to(socketId).emit("event", {
      error: true,
      data: `linedraw: \nerror: ${error.message}\n`,
    });
    console.log(`linedraw: error: ${error.message}`);
  });

  ls.on("close", (code) => {
    io.to(socketId).emit("event", {
      error: false,
      data: `linedraw: \nchild process exited with code ${code}\n`,
    });

    sharp(`./public/output/${nama_file}.svg`)
      .png()
      .toFile(`./public/output/${nama_file}.png`)
      .then(function (info) {
        console.log(info);
        io.to(socketId).emit("event", {
          error: false,
          data: info,
        });
        io.to(socketId).emit("hasil", {
          error: false,
          url: {
            svg: `output/${nama_file}.svg`,
            png: `output/${nama_file}.png`,
          },
          from: "linedraw",
        });
      })
      .catch(function (err) {
        console.log(err);
        io.to(socketId).emit("event", {
          error: true,
          data: err,
        });
      });

    console.log(`linedraw: child process exited with code ${code}`);
  });
}

//routing
app.get("/", (req, res) => {
  res.render("index.ejs", {
    root_path: process.env.ROOT || "",
    frontend_url: process.env.FRONTEND || "",
  });
});

app.post("/:socketId", function (req, res) {
  if (!req.params.socketId) {
    return res.status(400).send("Koneksi gagal, muat ulang halaman.");
  }
  if (!req.files || Object.keys(req.files).length === 0) {
    return res.status(400).send("No files were uploaded.");
  }
  let foto = req.files.foto;
  if (!foto.mimetype.includes("image")) {
    return res
      .status(400)
      .send(
        "Format file tidak di support, hanya menerima gambar, gunakan png, jpeg atau jpg."
      );
  }

  const nama_file = `${uuid()}_${foto.name}`;
  foto.mv(`./input/${nama_file}`, function (err) {
    if (err) return res.status(500).send(err);
    res.send({});
    linedraw(req.params.socketId, nama_file);
  });
});

io.on("connection", (socket) => {
  console.log(`koneksi pengguna terhubung, id = ${socket.id}`);
  socket.on("disconnect", () => {
    console.log(`koneksi pengguna terputus, id = ${socket.id}`);
  });
});

const port = process.env.PORT || 3000;
http.listen(port);
console.log(`server jalan di port ${port}`);
