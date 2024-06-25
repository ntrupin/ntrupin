const G = 6.67 * Math.pow(10, -11);

const scale = (n) => n == 0 
  ? 1 
  : Math.pow(10, Math.floor(Math.log10(Math.abs(n))));

class PhysicsBody {
  constructor(p, {
    name = "[Unnamed]",
    x = 0, y = 0, vx = 0, vy = 0, ax = 0, ay = 0,
    fx = 0, fy = 0, r = 0, m = 1,
    color = "black"
  }) {
    this.p = p;
    this.name = name;
    this.pos = p.createVector(x, y);
    this.vel = p.createVector(vx, vy);
    this.acc = p.createVector(ax, ay);
    this.f = p.createVector(fx, fy);
    this.lf = p.createVector(0, 0);
    this.r = r;
    this.m = m;
    this.color = color;
  }

  move(dt) {
    if (this.rigid) { return; }
    this.acc.set(this.f.copy().mult(1 / this.m));
    this.vel.add(this.acc.copy().mult(dt));
    this.pos.add(this.vel.copy().mult(dt));
  }

  display(center) {
    let sx = this.p.width / 2 + ((this.pos.x - center.pos.x) / (3.84 * Math.pow(10, 8))) * 100;
    let sy = this.p.height / 2 + ((this.pos.y - center.pos.y) / (3.84 * Math.pow(10, 8))) * 100;
    let sr = this.r / scale(this.r) * 5;
    this.p.circle(sx, sy, sr);
  }
}

class World {
  
}
