function draw_voltage_trace() {

    var margin = {top: 20, right: 20, bottom: 30, left: 50},
        width = 960 - margin.left - margin.right,
        height = 500 - margin.top - margin.bottom;

    var xScale = d3.scale.linear().range([0, width]).domain([0, d3.max(times)]),
        yScale = d3.scale.linear().range([height, 0]).domain([d3.min(d3.merge(data)), d3.max(d3.merge(data))]);

    var xAxis = d3.svg.axis().scale(xScale).orient("bottom").ticks(5),
        yAxis = d3.svg.axis().scale(yScale).orient("left").ticks(5);

    var color = d3.scale.category10().range();

    var line = d3.svg.line()
        .interpolate("monotone")
        .x(function(d, i) { return xScale(times[i]); })
        .y(function(d) { return yScale(d); });

    var svg = d3.select("body").append("svg:svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .attr("class", "voltmeter")
        .call(d3.behavior.zoom().x(xScale).scaleExtent([1, 10]).on("zoom", zoomed))
      .append("g")
        .attr("transform", "translate(" + margin.left + "," + margin.top + ")");


    svg.append("svg:defs").append("clipPath")
        .attr("id", "clip")
      .append("rect")
        .attr("width", width)
        .attr("height", height);


    for (var i = 0; i < data.length; i++) {
        svg.append("svg:path")
            .datum(data[i])
            .attr("class", "line")
            .attr("clip-path", "url(#clip)")
            .attr("d", line)
            .style("stroke", color[i % 10] );
    }

    svg.append("svg:text")
        .attr("class", "title")
        .attr("x", width/2-margin.left)
        .attr("y", -10)
        .text("Voltage trace");

    svg.append("svg:text")
        .attr("class", "x label")
        .attr("text-anchor", "middle")
        .attr("x", width/2)
        .attr("y", height+margin.bottom-12)
        .attr("dy", ".75em")
        .text("Time (ms)");

    svg.append("svg:text")
        .attr("class", "y label")
        .attr("text-anchor", "middle")
        .attr("x", -height/2)
        .attr("y", -(margin.left-5))
        .attr("dy", ".75em")
        .attr("transform", "rotate(-90)")
        .text("Membrane potential (mV)");

    svg.append("g")
        .attr("class", "x axis")
        .attr("transform", "translate(0," + height + ")")
        .call(xAxis);

    svg.append("g")
        .attr("class", "y axis")
        .call(yAxis);

    function zoomed() {
        svg.select(".x.axis").call(xAxis);
        svg.select(".y.axis").call(yAxis);
        svg.selectAll(".line").attr("d", line)
    }

}

